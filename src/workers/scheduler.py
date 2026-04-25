"""Celery: проверка расписаний раз в минуту (Beat) и проактивные сообщения в MAX."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from redis.asyncio import Redis
from sqlalchemy import select

from src.core.config import get_settings
from src.domain.entities import Schedule, ScheduleType
from src.infrastructure.database import AsyncSessionLocal
from src.infrastructure.models import MiniAppUserModel
from src.infrastructure.monitoring import get_chat_events_broadcaster
from src.infrastructure.repositories import (
    HybridChatMemoryRepository,
    PostgresSettingsRepository,
    RedisChatMemoryRepository,
    SqlAlchemyKnowledgeRepository,
    SqlAlchemyScheduleRepository,
)
from src.infrastructure.services.dynamic_llm import DynamicLLMService
from src.infrastructure.services.max_messenger import MaxMessengerClient
from src.infrastructure.services.max_proactive_delivery import MaxProactiveDeliveryMessenger
from src.infrastructure.services.openai_embedding import OpenAIEmbeddingService
from src.use_cases.proactive_schedule import ExecuteProactiveScheduleUseCase

logger = logging.getLogger(__name__)


def _interval_timedelta(cfg: dict) -> timedelta:
    """Интервал из JSON (дни/часы/минуты); нули допускаются."""
    days = int(cfg.get("days", 0) or 0)
    hours = int(cfg.get("hours", 0) or 0)
    minutes = int(cfg.get("minutes", 0) or 0)
    return timedelta(days=days, hours=hours, minutes=minutes)


def _minute_bucket_in_tz(tz: ZoneInfo, dt: datetime) -> tuple[int, int, int, int, int]:
    """Минута на «стене часов» в заданном поясе (для напоминаний и защиты от дублей)."""
    d = dt.astimezone(tz).replace(second=0, microsecond=0)
    return (d.year, d.month, d.day, d.hour, d.minute)


def _is_annual_event(event_data: dict) -> bool:
    return bool(event_data.get("annual") or event_data.get("ezhegodno"))


def _database_event_due(ev, tz: ZoneInfo, now: datetime) -> bool:
    """Совпадение календарной даты в часовом поясе приложения (Саратов и т.д.)."""
    now_local = now.astimezone(tz)
    ed = ev.event_datetime.astimezone(tz)
    data = ev.event_data or {}
    if _is_annual_event(data):
        if (ed.month, ed.day) != (now_local.month, now_local.day):
            return False
        if ev.last_triggered_at:
            lt = ev.last_triggered_at.astimezone(tz).date()
            if lt == now_local.date():
                return False
        return True
    return ed.date() == now_local.date()


def _reminder_due(schedule, ev, tz: ZoneInfo, now: datetime) -> bool:
    """Срабатывание в минуту ``event_datetime - offset`` по локальному времени приложения."""
    off = int(schedule.reminder_offset_minutes or 0)
    fire_at = ev.event_datetime - timedelta(minutes=off)
    return _minute_bucket_in_tz(tz, fire_at) == _minute_bucket_in_tz(tz, now)


def _interval_due(schedule, now: datetime) -> bool:
    delta = _interval_timedelta(schedule.interval_settings or {})
    if delta.total_seconds() <= 0:
        return False
    if schedule.last_run_at is None:
        return True
    last = schedule.last_run_at
    if not last.tzinfo:
        last = last.replace(tzinfo=timezone.utc)
    return (now.astimezone(timezone.utc) - last.astimezone(timezone.utc)) >= delta


def _same_minute_as_last_interval_run(schedule, tz: ZoneInfo, now: datetime) -> bool:
    """Защита от двойного срабатывания в одной минуте при повторном тике."""
    if schedule.last_run_at is None:
        return False
    return _minute_bucket_in_tz(tz, schedule.last_run_at) == _minute_bucket_in_tz(tz, now)


def _local_hhmm_matches(now: datetime, tz: ZoneInfo, time_s: str) -> bool:
    """Сравнение локального времени приложения с строкой «ЧЧ:ММ» (для дней рождения)."""
    raw = (time_s or "10:00").strip() or "10:00"
    parts = raw.split(":")
    try:
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
    except (TypeError, ValueError, IndexError):
        h, m = 10, 0
    h = max(0, min(23, h))
    m = max(0, min(59, m))
    local = now.astimezone(tz)
    return local.hour == h and local.minute == m


def _schedule_already_fired_today(sch: Schedule, tz: ZoneInfo, now: datetime) -> bool:
    if sch.last_run_at is None:
        return False
    last = sch.last_run_at
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return last.astimezone(tz).date() == now.astimezone(tz).date()


def _build_use_case(
    session,
    redis: Redis,
    settings,
) -> ExecuteProactiveScheduleUseCase:
    settings_repo = PostgresSettingsRepository(session, redis)
    inner = RedisChatMemoryRepository(redis, ttl_seconds=settings.chat_memory_ttl_seconds)
    memory = HybridChatMemoryRepository(inner, session)
    client = MaxMessengerClient(
        settings_repository=settings_repo,
        api_base_url=settings.max_api_base,
        platform_api_base_url=settings.max_platform_api_base,
        env_fallback_max_bot_token=settings.max_bot_token,
    )
    delivery = MaxProactiveDeliveryMessenger(client)
    return ExecuteProactiveScheduleUseCase(
        embedding_service=OpenAIEmbeddingService(settings=settings, settings_repo=settings_repo),
        knowledge_repository=SqlAlchemyKnowledgeRepository(session),
        llm_service=DynamicLLMService(settings=settings, settings_repo=settings_repo),
        chat_memory=memory,
        settings_repository=settings_repo,
        chat_monitoring=get_chat_events_broadcaster(),
        messenger=delivery,
    )


async def _check_and_execute_schedules_async() -> str:
    settings = get_settings()
    tz = settings.app_zoneinfo
    redis = Redis.from_url(settings.redis_uri, decode_responses=True)
    now = datetime.now(tz)
    try:
        async with AsyncSessionLocal() as session:
            repo = SqlAlchemyScheduleRepository(session)
            schedules = await repo.list_schedules(active_only=True)
            use_case = _build_use_case(session, redis, settings)
            now_label = now.astimezone(tz).strftime("%Y-%m-%d %H:%M")
            brief = [(s.id, s.type.value) for s in schedules if s.id is not None][:40]
            logger.info(
                "check_and_execute_schedules: активных=%s now_local=%s (APP_TIMEZONE=%s) id+type=%s",
                len(schedules),
                now_label,
                settings.app_timezone,
                brief,
            )

            for sch in schedules:
                if sch.id is None:
                    continue
                sid = sch.id

                if sch.type == ScheduleType.INTERVAL:
                    if not _interval_due(sch, now):
                        continue
                    if _same_minute_as_last_interval_run(sch, tz, now):
                        continue
                    try:
                        logger.info(
                            "Расписание [INTERVAL]: запуск id=%s chat_id=%s",
                            sid,
                            sch.chat_id,
                        )
                        await use_case.execute(sch, event=None)
                        await repo.update_last_run_at(sid, now)
                        await session.commit()
                    except Exception:
                        await session.rollback()
                        logger.exception("Расписание [INTERVAL]: ошибка id=%s", sid)
                    continue

                if sch.type == ScheduleType.DATABASE:
                    while True:
                        events = await repo.list_pending_events(sid)
                        picked = None
                        for ev in events:
                            if ev.id is None:
                                continue
                            if _database_event_due(ev, tz, now):
                                picked = ev
                                break
                        if picked is None:
                            break
                        try:
                            logger.info(
                                "Расписание [DATABASE]: запуск schedule_id=%s event_id=%s chat_id=%s",
                                sid,
                                picked.id,
                                sch.chat_id,
                            )
                            await use_case.execute(sch, event=picked)
                            data = picked.event_data or {}
                            if _is_annual_event(data):
                                await repo.update_event_last_triggered(picked.id, now)
                            else:
                                await repo.mark_event_processed(picked.id)
                            await session.commit()
                        except Exception:
                            await session.rollback()
                            logger.exception(
                                "Расписание [DATABASE]: ошибка schedule_id=%s event_id=%s",
                                sid,
                                picked.id,
                            )
                            break
                    continue

                if sch.type == ScheduleType.REMINDER:
                    while True:
                        events = await repo.list_pending_events(sid)
                        picked = None
                        for ev in events:
                            if ev.id is None:
                                continue
                            if _reminder_due(sch, ev, tz, now):
                                picked = ev
                                break
                        if picked is None:
                            break
                        try:
                            logger.info(
                                "Расписание [REMINDER]: запуск schedule_id=%s event_id=%s chat_id=%s",
                                sid,
                                picked.id,
                                sch.chat_id,
                            )
                            await use_case.execute(sch, event=picked)
                            await repo.mark_event_processed(picked.id)
                            await session.commit()
                        except Exception:
                            await session.rollback()
                            logger.exception(
                                "Расписание [REMINDER]: ошибка schedule_id=%s event_id=%s",
                                sid,
                                picked.id,
                            )
                            break
                    continue

                if sch.type == ScheduleType.MINIAPP_BIRTHDAYS:
                    cfg = sch.interval_settings or {}
                    org_id_s = (cfg.get("organization_id") or "").strip()
                    if not org_id_s:
                        logger.info(
                            "MINIAPP_BIRTHDAYS: пропуск schedule_id=%s — пустой organization_id (now_local=%s %s)",
                            sid,
                            now_label,
                            settings.app_timezone,
                        )
                        continue
                    try:
                        org_uid = UUID(org_id_s)
                        org_id_s = str(org_uid)
                    except (TypeError, ValueError):
                        logger.warning(
                            "Расписание [MINIAPP_BIRTHDAYS]: неверный organization_id schedule_id=%s",
                            sid,
                        )
                        continue
                    time_label = (str(cfg.get("greeting_time") or "10:00").strip() or "10:00")
                    time_ok = _local_hhmm_matches(now, tz, time_label)
                    already = _schedule_already_fired_today(sch, tz, now)
                    logger.info(
                        "MINIAPP_BIRTHDAYS: проверка schedule_id=%s org=%s greeting_time=%r now_local=%s time_match=%s already_fired_today=%s last_run_at=%s",
                        sid,
                        org_id_s,
                        time_label,
                        f"{now_label} ({settings.app_timezone})",
                        time_ok,
                        already,
                        sch.last_run_at,
                    )
                    if not time_ok:
                        continue
                    if already:
                        logger.info(
                            "MINIAPP_BIRTHDAYS: пропуск schedule_id=%s — уже срабатывало сегодня (last_run_at=%s)",
                            sid,
                            sch.last_run_at,
                        )
                        continue
                    try:
                        u_rows = (
                            await session.execute(
                                select(MiniAppUserModel).where(
                                    MiniAppUserModel.organization_id == org_uid,
                                ),
                            )
                        ).scalars().all()
                    except Exception:
                        logger.exception("Расписание [MINIAPP_BIRTHDAYS]: запрос users schedule_id=%s", sid)
                        continue
                    now_local = now.astimezone(tz)
                    birthday_today = 0
                    for _u in u_rows:
                        _bd = getattr(_u, "birth_date", None)
                        if _bd is not None and (_bd.month, _bd.day) == (now_local.month, now_local.day):
                            birthday_today += 1
                    logger.info(
                        "MINIAPP_BIRTHDAYS: users schedule_id=%s org=%s total_users=%s birthday_today=%s",
                        sid,
                        org_id_s,
                        len(u_rows),
                        birthday_today,
                    )
                    group_raw = (cfg.get("group_chat_id") or "").strip()
                    group_chat_id = group_raw or None
                    ran_ok = False
                    for u in u_rows:
                        bd = getattr(u, "birth_date", None)
                        if bd is None:
                            continue
                        if (bd.month, bd.day) != (now_local.month, now_local.day):
                            continue
                        name = (u.name or "Пользователь").strip() or "Пользователь"
                        base_template = (sch.content_template or "").strip()
                        extra_personal = (
                            f"Сегодня день рождения у пользователя Mini App ({name}). "
                            f"Сформируй тёплое краткое поздравление в личный чат. "
                        )
                        sch_personal: Schedule = replace(
                            sch,
                            chat_id=str(u.chat_id).strip(),
                            content_template=extra_personal + base_template,
                        )
                        try:
                            logger.info(
                                "Расписание [MINIAPP_BIRTHDAYS]: личный чат schedule_id=%s user_chat_id=%s org=%s time=%s",
                                sid,
                                u.chat_id,
                                org_id_s,
                                time_label,
                            )
                            await use_case.execute(sch_personal, event=None)
                            await session.commit()
                            ran_ok = True
                        except Exception:
                            await session.rollback()
                            logger.exception(
                                "Расписание [MINIAPP_BIRTHDAYS]: ошибка (личный) schedule_id=%s chat_id=%s",
                                sid,
                                u.chat_id,
                            )
                        if group_chat_id is None:
                            continue
                        extra_group = (
                            f"Сегодня день рождения у пользователя Mini App: {name}. "
                            f"Сообщение пойдёт в групповой чат. Сформируй короткое уместное поздравление "
                            f"для группы: обязательно укажи имя именинника, тон нейтральный или на «вы», без излишней личной интимности. "
                        )
                        sch_group: Schedule = replace(
                            sch,
                            chat_id=group_chat_id,
                            content_template=extra_group + base_template,
                        )
                        try:
                            logger.info(
                                "Расписание [MINIAPP_BIRTHDAYS]: группа schedule_id=%s group_chat_id=%s именинник=%s",
                                sid,
                                group_chat_id,
                                name,
                            )
                            await use_case.execute(sch_group, event=None)
                            await session.commit()
                            ran_ok = True
                        except Exception:
                            await session.rollback()
                            logger.exception(
                                "Расписание [MINIAPP_BIRTHDAYS]: ошибка (группа) schedule_id=%s group_chat_id=%s",
                                sid,
                                group_chat_id,
                            )
                    # Отметка «сегодня сработали» — отдельной транзакцией, чтобы не откатывать успешные отправки.
                    try:
                        await repo.update_last_run_at(sid, now)
                        await session.commit()
                    except Exception:
                        await session.rollback()
                        if ran_ok:
                            logger.exception("Расписание [MINIAPP_BIRTHDAYS]: commit last_run id=%s", sid)
                    continue
    finally:
        # Celery вызывает asyncio.run() на каждый тик: пул asyncpg привязан к loop — сбрасываем до уничтожения цикла.
        try:
            await redis.aclose()
        finally:
            from src.infrastructure.database import engine

            await engine.dispose()

    return "ok"


def run_schedules_sync() -> str:
    """Синхронная обёртка для Celery worker."""
    return asyncio.run(_check_and_execute_schedules_async())
