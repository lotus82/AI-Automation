"""Асинхронная логика Beat для дедлайнов комплаенса (БД + MAX).

Вызывается из Celery через ``asyncio.run`` (см. ``src/workers/tasks.py``)."""

from __future__ import annotations

import logging
from datetime import date, datetime

from redis.asyncio import Redis
from sqlalchemy import select

from src.core.config import get_settings
from src.domain.portal_roles import ROLE_DIRECTOR, ROLE_ORG_ADMIN
from src.infrastructure.database import AsyncSessionLocal, engine
from src.infrastructure.models import (
    ComplianceDeadlineModel,
    ComplianceDeadlineStatus,
    LegalOrgType,
    LegalProfileModel,
    LegalTaxSystem,
    PortalUserModel,
)
from src.infrastructure.repositories.stores import PostgresSettingsRepository
from src.infrastructure.services.max_messenger import MaxMessengerClient

logger = logging.getLogger(__name__)

_TITLE_USN_ADVANCE = "Уплата авансового платежа по УСН"
_TITLE_RSV = "Отчет РСВ"

_REMINDER_DAYS = frozenset({7, 3, 1})


def _app_today() -> date:
    settings = get_settings()
    return datetime.now(settings.app_zoneinfo).date()


def _quarter_labels_and_usn_due_dates(base_year: int) -> list[tuple[str, date]]:
    """Квартал относится к календарному году ``base_year`` (Q1–Q3); Q4 → срок в январе ``base_year+1``."""

    y = base_year
    return [
        (f"{y}-Q1", date(y, 4, 28)),
        (f"{y}-Q2", date(y, 7, 28)),
        (f"{y}-Q3", date(y, 10, 28)),
        (f"{y}-Q4", date(y + 1, 1, 28)),
    ]


def _quarter_labels_and_rsv_due_dates(base_year: int) -> list[tuple[str, date]]:
    y = base_year
    return [
        (f"{y}-Q1", date(y, 4, 25)),
        (f"{y}-Q2", date(y, 7, 25)),
        (f"{y}-Q3", date(y, 10, 25)),
        (f"{y}-Q4", date(y + 1, 1, 25)),
    ]


def _profile_has_employees(profile: LegalProfileModel) -> bool:
    """Флаг из ``charter_rules`` или эвристика по ОПФ (ИП по умолчанию без сотрудников)."""

    cr = profile.charter_rules or {}
    if "has_employees" in cr:
        return bool(cr["has_employees"])
    return profile.org_type != LegalOrgType.IP


async def _deadline_exists(
    session,
    *,
    organization_id,
    title: str,
    due: date,
) -> bool:
    q = await session.execute(
        select(ComplianceDeadlineModel.id).where(
            ComplianceDeadlineModel.organization_id == organization_id,
            ComplianceDeadlineModel.title == title,
            ComplianceDeadlineModel.due_date == due,
        ).limit(1),
    )
    return q.scalar_one_or_none() is not None


async def _create_deadline(
    session,
    *,
    organization_id,
    title: str,
    due: date,
    description: str,
) -> None:
    row = ComplianceDeadlineModel(
        organization_id=organization_id,
        title=title,
        due_date=due,
        status=ComplianceDeadlineStatus.PENDING,
        description=description,
    )
    session.add(row)
    await session.flush()


async def _ensure_profile_deadlines(session, profile: LegalProfileModel, today: date) -> int:
    """Создаёт отсутствующие дедлайны; возвращает число новых строк."""

    created = 0
    oid = profile.organization_id
    years = range(today.year - 1, today.year + 2)

    if profile.tax_system == LegalTaxSystem.USN_INCOME:
        for y in years:
            for period_label, due in _quarter_labels_and_usn_due_dates(y):
                if due < today:
                    continue
                if await _deadline_exists(session, organization_id=oid, title=_TITLE_USN_ADVANCE, due=due):
                    continue
                await _create_deadline(
                    session,
                    organization_id=oid,
                    title=_TITLE_USN_ADVANCE,
                    due=due,
                    description=f"Автогенерация: {period_label}, УСН «доходы», срок до {due.isoformat()}.",
                )
                created += 1

    if _profile_has_employees(profile):
        for y in years:
            for period_label, due in _quarter_labels_and_rsv_due_dates(y):
                if due < today:
                    continue
                if await _deadline_exists(session, organization_id=oid, title=_TITLE_RSV, due=due):
                    continue
                await _create_deadline(
                    session,
                    organization_id=oid,
                    title=_TITLE_RSV,
                    due=due,
                    description=f"Автогенерация: {period_label}, РСВ, срок до {due.isoformat()}.",
                )
                created += 1

    return created


async def generate_compliance_deadlines_async() -> str:
    today = _app_today()
    total_new = 0
    profiles: list[LegalProfileModel] = []
    try:
        async with AsyncSessionLocal() as session:
            result = await session.scalars(select(LegalProfileModel))
            profiles = list(result)

            for profile in profiles:
                try:
                    n = await _ensure_profile_deadlines(session, profile, today)
                    if n:
                        await session.commit()
                        total_new += n
                        logger.info(
                            "Комплаенс: создано дедлайнов=%s org_id=%s",
                            n,
                            profile.organization_id,
                        )
                    else:
                        await session.rollback()
                except Exception:
                    await session.rollback()
                    logger.exception(
                        "Комплаенс: ошибка генерации дедлайнов org_id=%s",
                        profile.organization_id,
                    )
    finally:
        await engine.dispose()

    logger.info(
        "generate_compliance_deadlines: профилей=%s, новых_дедлайнов=%s, today=%s",
        len(profiles),
        total_new,
        today.isoformat(),
    )
    return f"profiles={len(profiles)} new_deadlines={total_new}"


def _role_sort_key(user: PortalUserModel) -> tuple[int, str]:
    role = (user.role or "").strip()
    if role == ROLE_ORG_ADMIN:
        order = 0
    elif role == ROLE_DIRECTOR:
        order = 1
    else:
        order = 2
    return (order, (user.username or "").lower())


async def _primary_max_chat_id(session, organization_id) -> int | None:
    """Один получатель: org_admin → director → прочие с привязкой MAX."""

    q = await session.scalars(
        select(PortalUserModel).where(
            PortalUserModel.organization_id == organization_id,
            PortalUserModel.is_active.is_(True),
            PortalUserModel.miniapp_chat_id.isnot(None),
        ),
    )
    users = [u for u in q if (u.miniapp_chat_id or "").strip()]
    if not users:
        return None
    users.sort(key=_role_sort_key)
    top = users[0]
    raw = str(top.miniapp_chat_id).strip()
    try:
        return int(raw)
    except (TypeError, ValueError):
        logger.warning(
            "Комплаенс: некорректный miniapp_chat_id user_id=%s org_id=%s",
            top.id,
            organization_id,
        )
        return None


async def notify_upcoming_deadlines_async() -> str:
    settings = get_settings()
    today = _app_today()
    redis = Redis.from_url(settings.redis_uri, decode_responses=True)
    sent = 0
    skipped = 0
    try:
        async with AsyncSessionLocal() as session:
            repo = PostgresSettingsRepository(session, redis)
            max_client = MaxMessengerClient(
                settings_repository=repo,
                api_base_url=settings.max_api_base,
                platform_api_base_url=settings.max_platform_api_base,
                env_fallback_max_bot_token=settings.max_bot_token,
            )

            q = await session.scalars(
                select(ComplianceDeadlineModel).where(
                    ComplianceDeadlineModel.status == ComplianceDeadlineStatus.PENDING,
                ),
            )
            rows = list(q)

            for dl in rows:
                try:
                    delta = (dl.due_date - today).days
                    if delta not in _REMINDER_DAYS:
                        continue

                    chat_id = await _primary_max_chat_id(session, dl.organization_id)
                    if chat_id is None:
                        logger.warning(
                            "Комплаенс: нет получателя MAX org_id=%s deadline_id=%s",
                            dl.organization_id,
                            dl.id,
                        )
                        skipped += 1
                        continue

                    # Токена может не быть в глобальных настройках
                    token = await max_client.resolve_bot_token()
                    if not token:
                        logger.error(
                            "Комплаенс: MAX_BOT_TOKEN не задан, напоминание не отправлено deadline_id=%s",
                            dl.id,
                        )
                        skipped += 1
                        continue

                    text = (
                        f"Напоминание: Срок сдачи '{dl.title}' истекает {dl.due_date.strftime('%d.%m.%Y')}"
                    )
                    await max_client.send_message(chat_id, text)
                    sent += 1
                    logger.info(
                        "Комплаенс: напоминание delta_days=%s deadline_id=%s org_id=%s chat_id=%s",
                        delta,
                        dl.id,
                        dl.organization_id,
                        chat_id,
                    )
                except Exception:
                    skipped += 1
                    logger.exception(
                        "Комплаенс: сбой уведомления deadline_id=%s org_id=%s",
                        getattr(dl, "id", None),
                        getattr(dl, "organization_id", None),
                    )
    finally:
        try:
            await redis.aclose()
        finally:
            await engine.dispose()

    logger.info(
        "notify_upcoming_deadlines: today=%s отправлено=%s пропущено=%s",
        today.isoformat(),
        sent,
        skipped,
    )
    return f"sent={sent} skipped={skipped}"
