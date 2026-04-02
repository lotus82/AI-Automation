"""ORM-модели SQLAlchemy, соответствующие доменным сущностям."""

from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
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
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(255))
    phone_number: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
    )


class CallRecordModel(Base):
    """История сессий: транскрипт для аналитики и интеграций."""

    __tablename__ = "call_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    duration: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    status: Mapped[str] = mapped_column(String(32))
    transcript_text: Mapped[str] = mapped_column(Text())
    direction: Mapped[str] = mapped_column(String(16), server_default=text("'web'"))
    remote_phone: Mapped[str] = mapped_column(String(64), server_default=text("''"))
    audio_filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
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
        server_default=text("gen_random_uuid()"),
    )
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), server_default=text("'pending'"))
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
    )


class TrainingScenarioModel(Base):
    """Сценарии тренажёра (создаёт РОП)."""

    __tablename__ = "training_scenarios"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    title: Mapped[str] = mapped_column(String(512))
    client_persona_prompt: Mapped[str] = mapped_column(Text())
    objections_to_raise: Mapped[str] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
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
        server_default=text("gen_random_uuid()"),
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
        server_default=text("now()"),
    )

    scenario: Mapped["TrainingScenarioModel"] = relationship(
        "TrainingScenarioModel",
        back_populates="training_sessions",
    )


class CallAnalyticsModel(Base):
    """Оценка и рекомендации ОКК по записи звонка/чата."""

    __tablename__ = "call_analytics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
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
        server_default=text("now()"),
    )

    call_record: Mapped["CallRecordModel"] = relationship(
        "CallRecordModel",
        back_populates="analytics",
    )


class SystemSettingModel(Base):
    """Динамические настройки (LLM, промпты, ключи API) — правка из панели.

    Известные ключи см. ``src.domain.system_setting_keys`` (в т.ч. **MAX_BOT_TOKEN**, **MAX_CONTEXT_LIMIT**, **TEXT_BOT_SYSTEM_SUPPLEMENT**).
    """

    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    description: Mapped[str] = mapped_column(String(512), nullable=False, server_default=text("''"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        onupdate=func.now(),
    )


class ChatMessageModel(Base):
    """История сообщений чат-ботов (MAX, будущий Telegram и т.д.) — источник для мониторинга и ОКК."""

    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    session_id: Mapped[str] = mapped_column(String(128), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text())
    user_display: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
    )


class KnowledgeItemModel(Base):
    """Таблица элементов знаний с опциональным вектором для pgvector."""

    __tablename__ = "knowledge_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    title: Mapped[str] = mapped_column(String(512))
    content: Mapped[str] = mapped_column(Text())
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(KNOWLEDGE_EMBEDDING_DIM),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )
