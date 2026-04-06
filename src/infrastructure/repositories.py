"""Реализации репозиториев на async SQLAlchemy и Redis."""

from __future__ import annotations

import json
import re

from redis.asyncio import Redis
from sqlalchemy import desc, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

import uuid
from uuid import UUID

from datetime import datetime, timezone

from src.core.config import get_settings
from src.domain import system_setting_keys as sk
from src.domain.entities import (
    CallAnalytics,
    CallRecord,
    ChatMessage,
    ChatSessionSummary,
    DialerQueueItem,
    DialerQueueStatus,
    KnowledgeItem,
    Lead,
    LeadStatus,
    Schedule,
    ScheduleType,
    ScheduledEvent,
    SystemSetting,
    TrainingScenario,
    TrainingSession,
)
from src.infrastructure.models import (
    KNOWLEDGE_EMBEDDING_DIM,
    CallAnalyticsModel,
    CallRecordModel,
    ChatMessageModel,
    DialerQueueModel,
    KnowledgeItemModel,
    LeadModel,
    ScheduleModel,
    ScheduledEventModel,
    SystemSettingModel,
    TrainingScenarioModel,
    TrainingSessionModel,
)
from src.use_cases.interfaces import (
    ICallRecordRepository,
    IChatMemoryRepository,
    IChatSessionQueryRepository,
    IDialerQueueRepository,
    IKnowledgeRepository,
    ILeadRepository,
    IScheduleRepository,
    ISettingsRepository,
    ITrainingScenarioRepository,
    ITrainingSessionRepository,
)


def _lead_to_domain(row: LeadModel) -> Lead:
    return Lead(
        id=row.id,
        name=row.name,
        phone_number=row.phone_number,
        status=LeadStatus(row.status),
        created_at=row.created_at,
    )


def _embedding_to_list(value: object | None) -> list[float] | None:
    if value is None:
        return None
    return [float(x) for x in value]


def _call_record_to_domain(row: CallRecordModel) -> CallRecord:
    return CallRecord(
        id=row.id,
        session_id=row.session_id,
        duration=row.duration,
        status=row.status,
        transcript_text=row.transcript_text,
        direction=row.direction,
        remote_phone=row.remote_phone,
        created_at=row.created_at,
        audio_filename=row.audio_filename,
    )


def _call_analytics_to_domain(row: CallAnalyticsModel) -> CallAnalytics:
    return CallAnalytics(
        id=row.id,
        call_record_id=row.call_record_id,
        score=row.score,
        recommendations=row.recommendations,
        created_at=row.created_at,
    )


def _knowledge_to_domain(row: KnowledgeItemModel) -> KnowledgeItem:
    return KnowledgeItem(
        id=row.id,
        title=row.title,
        content=row.content,
        embedding=_embedding_to_list(row.embedding),
        created_at=getattr(row, "created_at", None),
        description=getattr(row, "description", None),
    )


class SqlAlchemyLeadRepository(ILeadRepository):
    """Репозиторий лидов."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, lead: Lead) -> Lead:
        if lead.id is not None:
            msg = "Обновление существующего лида в этой версии не поддерживается"
            raise ValueError(msg)

        model = LeadModel(
            name=lead.name.strip(),
            phone_number=lead.phone_number.strip(),
            status=lead.status.value,
            created_at=lead.created_at,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _lead_to_domain(model)


class SqlAlchemyCallRecordRepository(ICallRecordRepository):
    """Записи сессий и аналитика ОКК в PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, record: CallRecord) -> CallRecord:
        if record.id is not None:
            msg = "Обновление записи звонка в этой версии не поддерживается"
            raise ValueError(msg)
        cr_kwargs: dict = {
            "session_id": record.session_id.strip(),
            "duration": record.duration,
            "status": record.status,
            "transcript_text": record.transcript_text,
            "direction": (record.direction or "web").strip(),
            "remote_phone": (record.remote_phone or "").strip(),
        }
        if record.created_at is not None:
            cr_kwargs["created_at"] = record.created_at
        model = CallRecordModel(**cr_kwargs)
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _call_record_to_domain(model)

    async def get_by_id(self, call_id: UUID) -> CallRecord | None:
        row = await self._session.get(CallRecordModel, call_id)
        return _call_record_to_domain(row) if row is not None else None

    async def update_audio_filename(self, call_id: UUID, filename: str | None) -> None:
        await self._session.execute(
            update(CallRecordModel)
            .where(CallRecordModel.id == call_id)
            .values(audio_filename=filename)
        )

    async def save_analytics(self, row: CallAnalytics) -> CallAnalytics:
        if row.id is not None:
            msg = "Обновление аналитики в этой версии не поддерживается"
            raise ValueError(msg)
        ca_kwargs: dict = {
            "call_record_id": row.call_record_id,
            "score": row.score,
            "recommendations": row.recommendations,
        }
        if row.created_at is not None:
            ca_kwargs["created_at"] = row.created_at
        model = CallAnalyticsModel(**ca_kwargs)
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _call_analytics_to_domain(model)

    async def list_recent_with_analytics(
        self,
        *,
        limit: int = 100,
    ) -> list[tuple[CallRecord, CallAnalytics | None]]:
        stmt = (
            select(CallRecordModel, CallAnalyticsModel)
            .outerjoin(
                CallAnalyticsModel,
                CallRecordModel.id == CallAnalyticsModel.call_record_id,
            )
            .order_by(CallRecordModel.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        out: list[tuple[CallRecord, CallAnalytics | None]] = []
        for rec_row, an_row in result.all():
            dom_r = _call_record_to_domain(rec_row)
            dom_a = _call_analytics_to_domain(an_row) if an_row is not None else None
            out.append((dom_r, dom_a))
        return out

    async def delete_by_id(self, call_id: UUID) -> bool:
        row = await self._session.get(CallRecordModel, call_id)
        if row is None:
            return False
        await self._session.delete(row)
        await self._session.flush()
        return True


class SqlAlchemyKnowledgeRepository(IKnowledgeRepository):
    """Репозиторий элементов знаний."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, item: KnowledgeItem) -> KnowledgeItem:
        if item.id is not None:
            msg = "Обновление элемента знаний в этой версии не поддерживается"
            raise ValueError(msg)

        model = KnowledgeItemModel(
            title=item.title.strip(),
            content=item.content,
            description=(item.description or "").strip() or None,
            embedding=item.embedding,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _knowledge_to_domain(model)

    async def search_similar(
        self,
        embedding: list[float],
        limit: int = 3,
    ) -> list[KnowledgeItem]:
        # Косинусное расстояние `<=>` в pgvector: меньше — ближе по смыслу
        if len(embedding) != KNOWLEDGE_EMBEDDING_DIM:
            msg = (
                f"Размерность вектора {len(embedding)} не совпадает с ожидаемой "
                f"{KNOWLEDGE_EMBEDDING_DIM}"
            )
            raise ValueError(msg)

        stmt = (
            select(KnowledgeItemModel)
            .where(KnowledgeItemModel.embedding.is_not(None))
            .order_by(KnowledgeItemModel.embedding.cosine_distance(embedding))
            .limit(limit)
        )
        result = await self._session.scalars(stmt)
        return [_knowledge_to_domain(row) for row in result.all()]

    async def list_recent(self, *, limit: int = 500) -> list[KnowledgeItem]:
        stmt = (
            select(KnowledgeItemModel)
            .order_by(KnowledgeItemModel.created_at.desc())
            .limit(min(max(1, limit), 1000))
        )
        result = await self._session.scalars(stmt)
        return [_knowledge_to_domain(row) for row in result.all()]

    async def delete_by_id(self, item_id: UUID) -> bool:
        from sqlalchemy import delete

        stmt = delete(KnowledgeItemModel).where(KnowledgeItemModel.id == item_id)
        res = await self._session.execute(stmt)
        await self._session.flush()
        return res.rowcount > 0


# Префикс ключа и TTL по умолчанию (сутки) — не даём старым сессиям бесконечно занимать RAM на VPS.
_CHAT_SESSION_KEY_PREFIX = "chat_session:"
_DEFAULT_CHAT_TTL_SECONDS = 24 * 3600


class RedisChatMemoryRepository(IChatMemoryRepository):
    """История диалога в Redis: список JSON-объектов {role, content} на ключ сессии."""

    def __init__(
        self,
        redis: Redis,
        *,
        ttl_seconds: int = _DEFAULT_CHAT_TTL_SECONDS,
    ) -> None:
        self._redis = redis
        self._ttl = ttl_seconds

    def _key(self, session_id: str) -> str:
        return f"{_CHAT_SESSION_KEY_PREFIX}{session_id}"

    async def get_history(self, session_id: str, *, limit: int | None = None) -> list[dict]:
        key = self._key(session_id)
        raw_messages = await self._redis.lrange(key, 0, -1)
        history: list[dict] = []
        for raw in raw_messages:
            try:
                history.append(json.loads(raw))
            except (json.JSONDecodeError, TypeError):
                # Повреждённая запись — пропускаем, чтобы не ломать весь диалог
                continue
        if limit is not None and limit > 0 and len(history) > limit:
            return history[-limit:]
        return history

    async def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        *,
        user_display: str | None = None,
    ) -> None:
        if role not in ("user", "assistant"):
            msg = "role должен быть 'user' или 'assistant'"
            raise ValueError(msg)
        key = self._key(session_id)
        obj: dict = {"role": role, "content": content}
        if user_display and role == "user":
            obj["user_display"] = user_display
        payload = json.dumps(obj, ensure_ascii=False)
        await self._redis.rpush(key, payload)
        await self._redis.expire(key, self._ttl)


def _row_to_chat_message_dict(row: ChatMessageModel) -> dict:
    d: dict = {"role": row.role, "content": row.content}
    if row.user_display:
        d["user_display"] = row.user_display
    return d


class HybridChatMemoryRepository(IChatMemoryRepository):
    """Redis (горячий кэш) + PostgreSQL (``chat_messages``) для всех текстовых каналов."""

    def __init__(
        self,
        redis_backend: RedisChatMemoryRepository,
        session: AsyncSession,
    ) -> None:
        self._redis = redis_backend
        self._session = session

    async def get_history(self, session_id: str, *, limit: int | None = None) -> list[dict]:
        sid = session_id.strip()
        if limit is not None and limit > 0:
            stmt = (
                select(ChatMessageModel)
                .where(ChatMessageModel.session_id == sid)
                .order_by(desc(ChatMessageModel.created_at), desc(ChatMessageModel.id))
                .limit(limit)
            )
            result = await self._session.scalars(stmt)
            rows = list(result.all())
            if rows:
                return [_row_to_chat_message_dict(r) for r in reversed(rows)]
            return await self._redis.get_history(session_id, limit=limit)

        stmt = (
            select(ChatMessageModel)
            .where(ChatMessageModel.session_id == sid)
            .order_by(ChatMessageModel.created_at.asc(), ChatMessageModel.id.asc())
        )
        result = await self._session.scalars(stmt)
        rows = list(result.all())
        if rows:
            return [_row_to_chat_message_dict(r) for r in rows]
        return await self._redis.get_history(session_id, limit=None)

    async def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        *,
        user_display: str | None = None,
    ) -> None:
        await self._redis.save_message(
            session_id, role, content, user_display=user_display
        )
        sid = session_id.strip()
        ud = user_display if role == "user" else None
        row = ChatMessageModel(
            session_id=sid,
            role=role,
            content=content,
            user_display=(ud.strip() if ud else None) or None,
        )
        self._session.add(row)
        await self._session.flush()


_SESSION_SUMMARIES_SQL = text("""
SELECT session_id, last_preview, last_at, user_label FROM (
  SELECT DISTINCT ON (session_id)
    session_id,
    content AS last_preview,
    created_at AS last_at,
    (
      SELECT cm2.user_display FROM chat_messages cm2
      WHERE cm2.session_id = chat_messages.session_id
        AND cm2.role = 'user'
        AND cm2.user_display IS NOT NULL
        AND trim(cm2.user_display) <> ''
      ORDER BY cm2.created_at DESC NULLS LAST
      LIMIT 1
    ) AS user_label
  FROM chat_messages
  ORDER BY session_id, created_at DESC, id DESC
) AS sub
ORDER BY last_at DESC NULLS LAST
LIMIT :lim
""")


class SqlAlchemyChatSessionRepository(IChatSessionQueryRepository):
    """Сводки и полная история из ``chat_messages``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_session_summaries(self, *, limit: int = 200) -> list[ChatSessionSummary]:
        lim = max(1, min(limit, 500))
        result = await self._session.execute(_SESSION_SUMMARIES_SQL, {"lim": lim})
        out: list[ChatSessionSummary] = []
        for row in result.mappings().all():
            raw_preview = row["last_preview"] or ""
            preview = raw_preview[:280] + ("…" if len(raw_preview) > 280 else "")
            out.append(
                ChatSessionSummary(
                    session_id=str(row["session_id"]),
                    last_preview=preview,
                    last_at=row["last_at"],
                    user_label=row["user_label"],
                )
            )
        return out

    async def list_messages_chronological(self, session_id: str) -> list[ChatMessage]:
        sid = session_id.strip()
        stmt = (
            select(ChatMessageModel)
            .where(ChatMessageModel.session_id == sid)
            .order_by(ChatMessageModel.created_at.asc(), ChatMessageModel.id.asc())
        )
        result = await self._session.scalars(stmt)
        return [
            ChatMessage(
                id=r.id,
                session_id=r.session_id,
                role=r.role,
                content=r.content,
                user_display=r.user_display,
                created_at=r.created_at,
            )
            for r in result.all()
        ]


def _training_scenario_to_domain(row: TrainingScenarioModel) -> TrainingScenario:
    return TrainingScenario(
        id=row.id,
        title=row.title,
        client_persona_prompt=row.client_persona_prompt,
        objections_to_raise=row.objections_to_raise,
        created_at=row.created_at,
    )


class SqlAlchemyTrainingScenarioRepository(ITrainingScenarioRepository):
    """Сценарии тренажёра в PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_recent(self, *, limit: int = 100) -> list[TrainingScenario]:
        stmt = (
            select(TrainingScenarioModel)
            .order_by(TrainingScenarioModel.created_at.desc())
            .limit(limit)
        )
        result = await self._session.scalars(stmt)
        return [_training_scenario_to_domain(r) for r in result.all()]

    async def get_by_id(self, scenario_id: UUID) -> TrainingScenario | None:
        row = await self._session.get(TrainingScenarioModel, scenario_id)
        return _training_scenario_to_domain(row) if row else None

    async def save(self, scenario: TrainingScenario) -> TrainingScenario:
        if scenario.id is not None:
            msg = "Обновление сценария в этой версии не поддерживается"
            raise ValueError(msg)
        model = TrainingScenarioModel(
            title=scenario.title.strip(),
            client_persona_prompt=scenario.client_persona_prompt.strip(),
            objections_to_raise=scenario.objections_to_raise.strip(),
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _training_scenario_to_domain(model)


class SqlAlchemyTrainingSessionRepository(ITrainingSessionRepository):
    """Результаты тренировок в PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, row: TrainingSession) -> TrainingSession:
        if row.id is not None:
            msg = "Обновление training_session в этой версии не поддерживается"
            raise ValueError(msg)
        model = TrainingSessionModel(
            scenario_id=row.scenario_id,
            manager_name=row.manager_name.strip() or "—",
            session_id=row.session_id.strip(),
            score=row.score,
            feedback_text=row.feedback_text.strip(),
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return TrainingSession(
            id=model.id,
            scenario_id=model.scenario_id,
            manager_name=model.manager_name,
            session_id=model.session_id,
            score=model.score,
            feedback_text=model.feedback_text,
            created_at=model.created_at,
        )


def _normalize_dialer_phone(raw: str) -> str:
    """Оставляет цифры и ведущий + для E.164-подобного вида."""
    s = (raw or "").strip()
    if not s:
        return ""
    s = re.sub(r"[^\d+]", "", s)
    if s.startswith("++"):
        s = "+" + s.lstrip("+")
    if len(re.sub(r"\D", "", s)) < 10:
        return ""
    return s[:32]


def _dialer_queue_to_domain(row: DialerQueueModel) -> DialerQueueItem:
    return DialerQueueItem(
        id=row.id,
        phone=row.phone,
        status=DialerQueueStatus(row.status),
        scheduled_at=row.scheduled_at,
        created_at=row.created_at,
    )


class SqlAlchemyDialerQueueRepository(IDialerQueueRepository):
    """Очередь автообзвона в PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_pending(self, *, limit: int = 50) -> list[DialerQueueItem]:
        stmt = (
            select(DialerQueueModel)
            .where(DialerQueueModel.status == DialerQueueStatus.PENDING.value)
            .order_by(DialerQueueModel.scheduled_at.asc())
            .limit(limit)
        )
        result = await self._session.scalars(stmt)
        return [_dialer_queue_to_domain(r) for r in result.all()]

    async def add_phones(self, phones: list[str]) -> int:
        inserted = 0
        for raw in phones:
            p = _normalize_dialer_phone(raw)
            if not p:
                continue
            self._session.add(
                DialerQueueModel(
                    phone=p,
                    status=DialerQueueStatus.PENDING.value,
                )
            )
            inserted += 1
        if inserted:
            await self._session.flush()
        return inserted

    async def set_status(self, item_id: UUID, status: DialerQueueStatus) -> None:
        row = await self._session.get(DialerQueueModel, item_id)
        if row is None:
            msg = f"Строка очереди {item_id} не найдена"
            raise ValueError(msg)
        row.status = status.value
        await self._session.flush()


def _schedule_to_domain(row: ScheduleModel) -> Schedule:
    return Schedule(
        id=row.id,
        chat_id=row.chat_id,
        is_active=bool(row.is_active),
        type=ScheduleType(row.schedule_type),
        prompt=row.prompt or "",
        content_template=row.content_template or "",
        interval_settings=dict(row.interval_settings or {}),
        reminder_offset_minutes=row.reminder_offset_minutes,
        last_run_at=row.last_run_at,
        created_at=row.created_at,
    )


def _event_to_domain(row: ScheduledEventModel) -> ScheduledEvent:
    return ScheduledEvent(
        id=row.id,
        schedule_id=row.schedule_id,
        event_datetime=row.event_datetime,
        event_data=dict(row.event_data or {}),
        is_processed=bool(row.is_processed),
        last_triggered_at=row.last_triggered_at,
    )


class SqlAlchemyScheduleRepository(IScheduleRepository):
    """Расписания и события в PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_schedules(self, *, active_only: bool = False) -> list[Schedule]:
        stmt = select(ScheduleModel).order_by(ScheduleModel.created_at.desc())
        if active_only:
            stmt = stmt.where(ScheduleModel.is_active.is_(True))
        result = await self._session.scalars(stmt)
        return [_schedule_to_domain(r) for r in result.all()]

    async def get_by_id(self, schedule_id: UUID) -> Schedule | None:
        row = await self._session.get(ScheduleModel, schedule_id)
        return _schedule_to_domain(row) if row else None

    async def create(self, schedule: Schedule) -> Schedule:
        if schedule.id is not None:
            msg = "Создание расписания: поле id должно быть None"
            raise ValueError(msg)
        new_id = uuid.uuid4()
        interval = schedule.interval_settings if schedule.interval_settings is not None else {}
        model = ScheduleModel(
            id=new_id,
            chat_id=schedule.chat_id.strip(),
            is_active=schedule.is_active,
            schedule_type=schedule.type.value,
            prompt=schedule.prompt or "",
            content_template=schedule.content_template or "",
            interval_settings=interval,
            reminder_offset_minutes=schedule.reminder_offset_minutes,
            last_run_at=schedule.last_run_at,
        )
        self._session.add(model)
        await self._session.flush()
        row = await self._session.get(ScheduleModel, new_id)
        assert row is not None
        return _schedule_to_domain(row)

    async def update(self, schedule: Schedule) -> Schedule | None:
        if schedule.id is None:
            msg = "Обновление расписания: нужен id"
            raise ValueError(msg)
        row = await self._session.get(ScheduleModel, schedule.id)
        if row is None:
            return None
        row.chat_id = schedule.chat_id.strip()
        row.is_active = schedule.is_active
        row.schedule_type = schedule.type.value
        row.prompt = schedule.prompt or ""
        row.content_template = schedule.content_template or ""
        row.interval_settings = dict(schedule.interval_settings or {})
        row.reminder_offset_minutes = schedule.reminder_offset_minutes
        await self._session.flush()
        refreshed = await self._session.get(ScheduleModel, schedule.id)
        assert refreshed is not None
        return _schedule_to_domain(refreshed)

    async def delete(self, schedule_id: UUID) -> bool:
        row = await self._session.get(ScheduleModel, schedule_id)
        if row is None:
            return False
        await self._session.delete(row)
        await self._session.flush()
        return True

    async def update_last_run_at(self, schedule_id: UUID, when: datetime) -> None:
        await self._session.execute(
            update(ScheduleModel)
            .where(ScheduleModel.id == schedule_id)
            .values(last_run_at=when),
        )
        await self._session.flush()

    async def list_pending_events(self, schedule_id: UUID) -> list[ScheduledEvent]:
        stmt = (
            select(ScheduledEventModel)
            .where(
                ScheduledEventModel.schedule_id == schedule_id,
                ScheduledEventModel.is_processed.is_(False),
            )
            .order_by(ScheduledEventModel.event_datetime.asc())
        )
        result = await self._session.scalars(stmt)
        return [_event_to_domain(r) for r in result.all()]

    async def add_events_bulk(self, schedule_id: UUID, events: list[ScheduledEvent]) -> int:
        n = 0
        for ev in events:
            self._session.add(
                ScheduledEventModel(
                    schedule_id=schedule_id,
                    event_datetime=ev.event_datetime,
                    event_data=dict(ev.event_data or {}),
                    is_processed=False,
                    last_triggered_at=ev.last_triggered_at,
                ),
            )
            n += 1
        await self._session.flush()
        return n

    async def mark_event_processed(self, event_id: UUID) -> None:
        await self._session.execute(
            update(ScheduledEventModel)
            .where(ScheduledEventModel.id == event_id)
            .values(is_processed=True),
        )
        await self._session.flush()

    async def update_event_last_triggered(self, event_id: UUID, when: datetime) -> None:
        await self._session.execute(
            update(ScheduledEventModel)
            .where(ScheduledEventModel.id == event_id)
            .values(last_triggered_at=when),
        )
        await self._session.flush()


def _system_setting_to_domain(row: SystemSettingModel) -> SystemSetting:
    return SystemSetting(
        key=row.key,
        value=row.value,
        description=row.description,
        updated_at=row.updated_at,
    )


class PostgresSettingsRepository(ISettingsRepository):
    """Настройки в PostgreSQL; горячие чтения кэшируются в Redis, при PUT ключ инвалидируется."""

    CACHE_PREFIX = "sys_setting:v1:"

    def __init__(self, session: AsyncSession, redis: Redis) -> None:
        self._session = session
        self._redis = redis

    def _cache_key(self, key: str) -> str:
        return f"{self.CACHE_PREFIX}{key.strip()}"

    async def get_value(self, key: str) -> str | None:
        k = key.strip()
        ck = self._cache_key(k)
        cached = await self._redis.get(ck)
        if cached is not None:
            return cached
        row = await self._session.get(SystemSettingModel, k)
        if row is None:
            return None
        await self._redis.set(ck, row.value)
        return row.value

    async def list_all(self) -> list[SystemSetting]:
        stmt = select(SystemSettingModel).order_by(SystemSettingModel.key.asc())
        result = await self._session.scalars(stmt)
        return [_system_setting_to_domain(r) for r in result.all()]

    async def upsert_values(self, updates: dict[str, str]) -> None:
        """Обновляет значения; для ключей из UPDATABLE_KEYS создаёт строку, если миграция-сид ещё не вставила её."""
        now = datetime.now(get_settings().app_zoneinfo)
        for raw_key, value in updates.items():
            k = raw_key.strip()
            row = await self._session.get(SystemSettingModel, k)
            if row is None:
                if k not in sk.UPDATABLE_KEYS:
                    msg = f"Неизвестный ключ настройки: {k}"
                    raise KeyError(msg)
                row = SystemSettingModel(
                    key=k,
                    value=value,
                    description="",
                    updated_at=now,
                )
                self._session.add(row)
            else:
                row.value = value
                row.updated_at = now
        await self._session.flush()
        for raw_key in updates:
            await self._redis.delete(self._cache_key(raw_key.strip()))
