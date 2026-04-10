"""ORM-модели SQLAlchemy, соответствующие доменным сущностям.

Все поля моментов времени — ``DateTime(timezone=True)`` (PostgreSQL ``timestamptz``).
В коде приложения при записи используйте только timezone-aware ``datetime``
(например ``datetime.now(get_settings().app_zoneinfo)`` из ``src.core.config``), без наивных значений.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func, text as sql_text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Размерность вектора под типичные эмбеддинги OpenAI; при смене локальной модели скорректировать миграцию.
# TODO: При выборе другой модели эмбеддингов изменить размерность столбца (новая миграция Alembic).
KNOWLEDGE_EMBEDDING_DIM = 1536


class Base(DeclarativeBase):
    """Базовый класс декларативных моделей."""


class LeadModel(Base):
    """Таблица лидов."""

    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sql_text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(255))
    phone_number: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sql_text("now()"),
    )


class CallRecordModel(Base):
    """История сессий: транскрипт для аналитики и интеграций."""

    __tablename__ = "call_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sql_text("gen_random_uuid()"),
    )
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    duration: Mapped[int] = mapped_column(Integer, server_default=sql_text("0"))
    status: Mapped[str] = mapped_column(String(32))
    transcript_text: Mapped[str] = mapped_column(Text())
    direction: Mapped[str] = mapped_column(String(16), server_default=sql_text("'web'"))
    remote_phone: Mapped[str] = mapped_column(String(64), server_default=sql_text("''"))
    audio_filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sql_text("now()"),
    )

    analytics: Mapped["CallAnalyticsModel | None"] = relationship(
        "CallAnalyticsModel",
        back_populates="call_record",
        uselist=False,
    )


class DialerQueueModel(Base):
    """Очередь номеров для исходящего автообзвона (Celery + SIP)."""

    __tablename__ = "dialer_queue"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sql_text("gen_random_uuid()"),
    )
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), server_default=sql_text("'pending'"))
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sql_text("now()"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sql_text("now()"),
    )


class TrainingScenarioModel(Base):
    """Сценарии тренажёра (создаёт РОП)."""

    __tablename__ = "training_scenarios"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sql_text("gen_random_uuid()"),
    )
    title: Mapped[str] = mapped_column(String(512))
    client_persona_prompt: Mapped[str] = mapped_column(Text())
    objections_to_raise: Mapped[str] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sql_text("now()"),
    )

    training_sessions: Mapped[list["TrainingSessionModel"]] = relationship(
        "TrainingSessionModel",
        back_populates="scenario",
    )


class TrainingSessionModel(Base):
    """Сессия тренировки: оценка менеджера после звонка с ИИ-клиентом."""

    __tablename__ = "training_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sql_text("gen_random_uuid()"),
    )
    scenario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("training_scenarios.id", ondelete="RESTRICT"),
        nullable=False,
    )
    manager_name: Mapped[str] = mapped_column(String(255))
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    feedback_text: Mapped[str] = mapped_column(Text(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sql_text("now()"),
    )

    scenario: Mapped["TrainingScenarioModel"] = relationship(
        "TrainingScenarioModel",
        back_populates="training_sessions",
    )


class TrainerMethodologyModel(Base):
    """Методика продаж (BANT, MEDDIC): описание и системный промпт роли клиента для симуляций."""

    __tablename__ = "trainer_methodologies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sql_text("gen_random_uuid()"),
    )
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text(), nullable=False, server_default=sql_text("''"))
    client_role_system_prompt: Mapped[str] = mapped_column(
        Text(),
        nullable=False,
        server_default=sql_text("''"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sql_text("now()"),
    )


class AiTrainerSessionModel(Base):
    """Сессия ИИ-тренера: пост-анализ транскрипта или инициация голосовой симуляции."""

    __tablename__ = "ai_trainer_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sql_text("gen_random_uuid()"),
    )
    manager_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    session_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    result_data: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sql_text("'{}'::jsonb"))
    methodology_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("trainer_methodologies.id", ondelete="SET NULL"),
        nullable=True,
    )
    scenario_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("training_scenarios.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sql_text("now()"),
    )


class QuestionnaireModel(Base):
    """Конструктор опросника и критерии для ИИ-оценки."""

    __tablename__ = "questionnaires"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sql_text("gen_random_uuid()"),
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    llm_criteria: Mapped[str] = mapped_column(Text(), nullable=False, server_default=sql_text("''"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sql_text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sql_text("now()"),
        onupdate=func.now(),
    )

    questions: Mapped[list["QuestionModel"]] = relationship(
        "QuestionModel",
        back_populates="questionnaire",
        cascade="all, delete-orphan",
    )


class QuestionModel(Base):
    """Вопрос опросника: single / multiple / text."""

    __tablename__ = "questions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sql_text("gen_random_uuid()"),
    )
    questionnaire_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("questionnaires.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    text: Mapped[str] = mapped_column(Text(), nullable=False)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    order: Mapped[int] = mapped_column(Integer(), nullable=False, server_default=sql_text("0"))
    min_score: Mapped[float] = mapped_column(Float(), nullable=False, server_default=sql_text("0"))
    max_score: Mapped[float] = mapped_column(Float(), nullable=False, server_default=sql_text("10"))

    questionnaire: Mapped["QuestionnaireModel"] = relationship(
        "QuestionnaireModel",
        back_populates="questions",
    )
    options: Mapped[list["QuestionOptionModel"]] = relationship(
        "QuestionOptionModel",
        back_populates="question",
        cascade="all, delete-orphan",
    )


class QuestionOptionModel(Base):
    """Вариант ответа для single/multiple."""

    __tablename__ = "question_options"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sql_text("gen_random_uuid()"),
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    text: Mapped[str] = mapped_column(Text(), nullable=False)
    score: Mapped[float] = mapped_column(Float(), nullable=False, server_default=sql_text("0"))

    question: Mapped["QuestionModel"] = relationship("QuestionModel", back_populates="options")


class CallAnalyticsModel(Base):
    """Оценка и рекомендации ОКК по записи звонка/чата."""

    __tablename__ = "call_analytics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sql_text("gen_random_uuid()"),
    )
    call_record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("call_records.id", ondelete="CASCADE"),
        unique=True,
    )
    score: Mapped[int] = mapped_column(Integer)
    recommendations: Mapped[str] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sql_text("now()"),
    )

    call_record: Mapped["CallRecordModel"] = relationship(
        "CallRecordModel",
        back_populates="analytics",
    )


class SystemSettingModel(Base):
    """Динамические настройки (LLM, промпты, ключи API) — правка из панели.

    Известные ключи см. ``src.domain.system_setting_keys`` (в т.ч. **LLM_TEMPERATURE**, **MAX_VOICE_REPLY_ENABLED**, **MAX_CALL_ANSWER_DELAY**, **MAX_CALL_GREETING_PHRASE**, **MAX_BOT_TOKEN**, **MAX_BOT_USERNAME**, **MAX_GROUP_CHAT_ID**, **MAX_GROUP_ADDITIONAL_PROMPT**, **MAX_CONTEXT_LIMIT**, **TEXT_BOT_SYSTEM_SUPPLEMENT**).
    """

    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text(), nullable=False, server_default=sql_text("''"))
    description: Mapped[str] = mapped_column(String(512), nullable=False, server_default=sql_text("''"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sql_text("now()"),
        onupdate=func.now(),
    )


class ScheduleModel(Base):
    """Проактивные рассылки в MAX: триггеры DATABASE / INTERVAL / REMINDER (фаза 18)."""

    __tablename__ = "schedules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sql_text("gen_random_uuid()"),
    )
    chat_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean(), nullable=False, server_default=sql_text("true"))
    schedule_type: Mapped[str] = mapped_column("type", String(32), nullable=False)
    prompt: Mapped[str] = mapped_column(Text(), nullable=False, server_default=sql_text("''"))
    content_template: Mapped[str] = mapped_column(Text(), nullable=False, server_default=sql_text("''"))
    interval_settings: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sql_text("'{}'::jsonb"))
    reminder_offset_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sql_text("now()"),
    )

    events: Mapped[list["ScheduledEventModel"]] = relationship(
        "ScheduledEventModel",
        back_populates="schedule",
        cascade="all, delete-orphan",
    )


class ScheduledEventModel(Base):
    """События для типов DATABASE и REMINDER (дни рождения, напоминания и т.п.)."""

    __tablename__ = "scheduled_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sql_text("gen_random_uuid()"),
    )
    schedule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schedules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    event_data: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sql_text("'{}'::jsonb"))
    is_processed: Mapped[bool] = mapped_column(Boolean(), nullable=False, server_default=sql_text("false"))
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    schedule: Mapped["ScheduleModel"] = relationship("ScheduleModel", back_populates="events")


class ChatMessageModel(Base):
    """История сообщений чат-ботов (MAX, будущий Telegram и т.д.) — источник для мониторинга и ОКК."""

    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sql_text("gen_random_uuid()"),
    )
    session_id: Mapped[str] = mapped_column(String(128), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text())
    user_display: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sql_text("now()"),
    )


class KnowledgeItemModel(Base):
    """Таблица элементов знаний с опциональным вектором для pgvector."""

    __tablename__ = "knowledge_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sql_text("gen_random_uuid()"),
    )
    title: Mapped[str] = mapped_column(String(512))
    content: Mapped[str] = mapped_column(Text())
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(KNOWLEDGE_EMBEDDING_DIM),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sql_text("now()"),
        nullable=False,
    )


class BitrixPortalModel(Base):
    """Портал Bitrix24 (Marketplace Server App): OAuth-токены для REST."""

    __tablename__ = "bitrix_portals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sql_text("gen_random_uuid()"),
    )
    portal_url: Mapped[str] = mapped_column(String(512), nullable=False, unique=True, index=True)
    member_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    access_token: Mapped[str] = mapped_column(Text(), nullable=False)
    refresh_token: Mapped[str] = mapped_column(Text(), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean(), nullable=False, server_default=sql_text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sql_text("now()"),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sql_text("now()"),
        onupdate=func.now(),
        nullable=False,
    )


class IntegrationModel(Base):
    """Универсальные интеграции с внешними API: auth / actions / webhooks в ``config`` (JSONB)."""

    __tablename__ = "integrations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sql_text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    base_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sql_text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sql_text("now()"),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sql_text("now()"),
        onupdate=func.now(),
        nullable=False,
    )
