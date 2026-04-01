"""Реализации репозиториев на async SQLAlchemy и Redis."""

from __future__ import annotations

import json
import re

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from uuid import UUID

from src.domain.entities import (
    CallAnalytics,
    CallRecord,
    DialerQueueItem,
    DialerQueueStatus,
    KnowledgeItem,
    Lead,
    LeadStatus,
    TrainingScenario,
    TrainingSession,
)
from src.infrastructure.models import (
    KNOWLEDGE_EMBEDDING_DIM,
    CallAnalyticsModel,
    CallRecordModel,
    DialerQueueModel,
    KnowledgeItemModel,
    LeadModel,
    TrainingScenarioModel,
    TrainingSessionModel,
)
from src.use_cases.interfaces import (
    ICallRecordRepository,
    IChatMemoryRepository,
    IDialerQueueRepository,
    IKnowledgeRepository,
    ILeadRepository,
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

    async def get_history(self, session_id: str) -> list[dict]:
        key = self._key(session_id)
        raw_messages = await self._redis.lrange(key, 0, -1)
        history: list[dict] = []
        for raw in raw_messages:
            try:
                history.append(json.loads(raw))
            except (json.JSONDecodeError, TypeError):
                # Повреждённая запись — пропускаем, чтобы не ломать весь диалог
                continue
        return history

    async def save_message(self, session_id: str, role: str, content: str) -> None:
        if role not in ("user", "assistant"):
            msg = "role должен быть 'user' или 'assistant'"
            raise ValueError(msg)
        key = self._key(session_id)
        payload = json.dumps(
            {"role": role, "content": content},
            ensure_ascii=False,
        )
        await self._redis.rpush(key, payload)
        await self._redis.expire(key, self._ttl)


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
