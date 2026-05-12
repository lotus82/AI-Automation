"""ORM-модели SQLAlchemy, соответствующие доменным сущностям.

Все поля моментов времени — ``DateTime(timezone=True)`` (PostgreSQL ``timestamptz``).
В коде приложения при записи используйте только timezone-aware ``datetime``
(например ``datetime.now(get_settings().app_zoneinfo)`` из ``src.core.config``), без наивных значений.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from typing import Any

from pgvector.sqlalchemy import Vector

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum as SQLEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text as sql_text,
)
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
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
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
    """Глобальные настройки экземпляра (супер-админ) и шаблон для копирования в организации.

    Известные ключи см. ``src.domain.system_setting_keys`` (в т.ч. **LLM_TEMPERATURE**, **MAX_VOICE_REPLY_ENABLED**, **MAX_CALL_ANSWER_DELAY**, **MAX_CALL_GREETING_PHRASE**, **MAX_BOT_TOKEN**, **MAX_BOT_USERNAME**, **MAX_GROUP_CHAT_PROMPTS**, **MAX_GROUP_CHAT_ID**, **MAX_GROUP_ADDITIONAL_PROMPT**, **MAX_CONTEXT_LIMIT**, **TEXT_BOT_SYSTEM_SUPPLEMENT**).
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


class OrganizationSettingModel(Base):
    """Настройки, изолированные по организации (промпты, ключи API, MAX и т.д.)."""

    __tablename__ = "organization_settings"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        primary_key=True,
    )
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
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
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
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
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


class OrganizationModel(Base):
    """Организация (тенант портала): изолированные учётные записи и политики."""

    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sql_text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    slug: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    inn: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        unique=True,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean(), nullable=False, server_default=sql_text("true"))
    # Активный сайт, отдаваемый в Mini App этой организации. ``NULL`` — сайт ещё не выбран.
    # ON DELETE SET NULL: если активный сайт удалён, организация остаётся без привязки.
    # use_alter=True + явное имя: между sites и organizations есть взаимные FK,
    # SQLAlchemy должен их «доспроить» после создания обеих таблиц.
    active_site_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="SET NULL", use_alter=True, name="fk_organizations_active_site_id"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sql_text("now()"),
        nullable=False,
    )

    shops: Mapped[list["ShopModel"]] = relationship("ShopModel", back_populates="organization")
    active_site: Mapped["SiteModel | None"] = relationship(
        "SiteModel",
        primaryjoin="OrganizationModel.active_site_id == SiteModel.id",
        foreign_keys="OrganizationModel.active_site_id",
        uselist=False,
        lazy="noload",
    )
    medical_doctors: Mapped[list["MedicalDoctorModel"]] = relationship(
        "MedicalDoctorModel",
        back_populates="organization",
    )
    medical_patients: Mapped[list["MedicalPatientModel"]] = relationship(
        "MedicalPatientModel",
        back_populates="organization",
    )


class PortalUserModel(Base):
    """Пользователь панели: супер-админ (organization_id NULL) или пользователь организации."""

    __tablename__ = "portal_users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sql_text("gen_random_uuid()"),
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    username: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    #: Идентификатор чата в MAX для сопоставления с Mini App (``mini_app_users.chat_id``).
    miniapp_chat_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    permissions: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sql_text("'{}'::jsonb"),
    )
    is_active: Mapped[bool] = mapped_column(Boolean(), nullable=False, server_default=sql_text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sql_text("now()"),
        nullable=False,
    )

    organization: Mapped["OrganizationModel | None"] = relationship(
        "OrganizationModel",
        lazy="joined",
    )
    medical_doctor_profile: Mapped["MedicalDoctorModel | None"] = relationship(
        "MedicalDoctorModel",
        back_populates="portal_user",
        uselist=False,
    )


class FormTemplateModel(Base):
    """Шаблон полей формы (регистрация, обратная связь) — JSON-конструктор."""

    __tablename__ = "form_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sql_text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text(), nullable=False, server_default=sql_text("''"))
    fields: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default=sql_text("'[]'::jsonb"))
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

    registration_events: Mapped[list["RegistrationEventModel"]] = relationship(
        "RegistrationEventModel",
        back_populates="form_template",
    )


class RegistrationEventModel(Base):
    """Мероприятие: своя форма (шаблон) и свои ответы; заголовок для публичной страницы."""

    __tablename__ = "registration_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sql_text("gen_random_uuid()"),
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    title_subtitle: Mapped[str] = mapped_column(Text(), nullable=False, server_default=sql_text("''"))
    form_template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("form_templates.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    event_start_date: Mapped[date] = mapped_column(Date(), nullable=False)
    event_end_date: Mapped[date] = mapped_column(Date(), nullable=False)
    registration_deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    registration_closed_early: Mapped[bool] = mapped_column(
        Boolean(),
        nullable=False,
        server_default=sql_text("false"),
    )
    notify_messenger: Mapped[str | None] = mapped_column(String(16), nullable=True)
    notify_chat_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
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

    form_template: Mapped["FormTemplateModel"] = relationship(
        "FormTemplateModel",
        back_populates="registration_events",
    )
    submissions: Mapped[list["RegistrationSubmissionModel"]] = relationship(
        "RegistrationSubmissionModel",
        back_populates="event",
        cascade="all, delete-orphan",
    )
    schedule_links: Mapped[list["RegistrationEventScheduleModel"]] = relationship(
        "RegistrationEventScheduleModel",
        back_populates="event",
        cascade="all, delete-orphan",
    )


class RegistrationEventScheduleModel(Base):
    """Привязка мероприятия к расписанию (напоминания и т.п.)."""

    __tablename__ = "registration_event_schedules"

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("registration_events.id", ondelete="CASCADE"),
        primary_key=True,
    )
    schedule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schedules.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )

    event: Mapped["RegistrationEventModel"] = relationship(
        "RegistrationEventModel",
        back_populates="schedule_links",
    )


class RegistrationSubmissionModel(Base):
    """Заполненная форма по конкретному мероприятию."""

    __tablename__ = "registration_submissions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sql_text("gen_random_uuid()"),
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("registration_events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    answers: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=sql_text("'{}'::jsonb"))
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sql_text("now()"),
        nullable=False,
    )

    event: Mapped["RegistrationEventModel"] = relationship(
        "RegistrationEventModel",
        back_populates="submissions",
    )


class ShopProductTag(str, enum.Enum):
    """Метка товара на витрине."""

    new = "new"
    sale = "sale"
    hot = "hot"


class ShopOrderStatus(str, enum.Enum):
    """Статус заказа магазина."""

    new = "new"
    paid = "paid"
    assembling = "assembling"
    delivering = "delivering"
    completed = "completed"


class ShopModel(Base):
    """Витрина магазина (мультиарендность: привязка к организации).

    Поле ``settings`` (JSONB): темы мессенджеров, контакты продавца, относительный путь логотипа и др.
    Рекомендуемые ключи: ``messenger_themes``, ``seller_max_chat_id``, ``seller_telegram_chat_id``,
    ``seller_vk_peer_id``, ``upload_logo_rel`` (файл в каталоге загрузок магазина).
    """

    __tablename__ = "shops"
    __table_args__ = (UniqueConstraint("organization_id", "slug", name="uq_shops_organization_slug"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sql_text("gen_random_uuid()"),
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text(), nullable=False, server_default=sql_text("''"))
    logo_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    settings: Mapped[dict[str, Any]] = mapped_column(
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

    organization: Mapped["OrganizationModel | None"] = relationship(
        "OrganizationModel",
        back_populates="shops",
    )
    categories: Mapped[list["CategoryModel"]] = relationship(
        "CategoryModel",
        back_populates="shop",
        cascade="all, delete-orphan",
    )
    products: Mapped[list["ProductModel"]] = relationship(
        "ProductModel",
        back_populates="shop",
        cascade="all, delete-orphan",
    )
    discounts: Mapped[list["DiscountModel"]] = relationship(
        "DiscountModel",
        back_populates="shop",
        cascade="all, delete-orphan",
    )
    orders: Mapped[list["OrderModel"]] = relationship(
        "OrderModel",
        back_populates="shop",
        cascade="all, delete-orphan",
    )
    static_pages: Mapped[list["StaticPageModel"]] = relationship(
        "StaticPageModel",
        back_populates="shop",
        cascade="all, delete-orphan",
    )


class CategoryModel(Base):
    """Категория товаров (дерево по ``parent_id``)."""

    __tablename__ = "shop_categories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sql_text("gen_random_uuid()"),
    )
    shop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shops.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shop_categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text(), nullable=False, server_default=sql_text("''"))
    order_index: Mapped[int] = mapped_column(Integer(), nullable=False, server_default=sql_text("0"))

    shop: Mapped["ShopModel"] = relationship("ShopModel", back_populates="categories")
    parent: Mapped["CategoryModel | None"] = relationship(
        "CategoryModel",
        remote_side=[id],
        foreign_keys=[parent_id],
        back_populates="children",
    )
    children: Mapped[list["CategoryModel"]] = relationship(
        "CategoryModel",
        back_populates="parent",
        foreign_keys=[parent_id],
        cascade="all, delete-orphan",
    )
    products: Mapped[list["ProductModel"]] = relationship("ProductModel", back_populates="category")


class ProductModel(Base):
    """Товар в витрине."""

    __tablename__ = "shop_products"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sql_text("gen_random_uuid()"),
    )
    shop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shops.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shop_categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text(), nullable=False, server_default=sql_text("''"))
    price: Mapped[Any] = mapped_column(Numeric(12, 2), nullable=False)
    photos: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default=sql_text("'[]'::jsonb"))
    stock_quantity: Mapped[int] = mapped_column(Integer(), nullable=False, server_default=sql_text("0"))
    tag: Mapped[ShopProductTag | None] = mapped_column(
        SQLEnum(ShopProductTag, name="shop_product_tag", native_enum=True, values_callable=lambda x: [e.value for e in x]),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean(), nullable=False, server_default=sql_text("true"))
    sort_order: Mapped[int] = mapped_column(Integer(), nullable=False, server_default=sql_text("0"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sql_text("now()"),
        nullable=False,
    )

    shop: Mapped["ShopModel"] = relationship("ShopModel", back_populates="products")
    category: Mapped["CategoryModel | None"] = relationship("CategoryModel", back_populates="products")


class DiscountModel(Base):
    """Скидка по магазину (период действия)."""

    __tablename__ = "shop_discounts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sql_text("gen_random_uuid()"),
    )
    shop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shops.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    percentage: Mapped[Any] = mapped_column(Numeric(5, 2), nullable=False)
    start_date: Mapped[date] = mapped_column(Date(), nullable=False)
    end_date: Mapped[date] = mapped_column(Date(), nullable=False)

    shop: Mapped["ShopModel"] = relationship("ShopModel", back_populates="discounts")


class OrderModel(Base):
    """Заказ покупателя."""

    __tablename__ = "shop_orders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sql_text("gen_random_uuid()"),
    )
    shop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shops.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[ShopOrderStatus] = mapped_column(
        SQLEnum(ShopOrderStatus, name="shop_order_status", native_enum=True, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=ShopOrderStatus.new,
    )
    customer_info: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=sql_text("'{}'::jsonb"))
    total_amount: Mapped[Any] = mapped_column(Numeric(14, 2), nullable=False, server_default=sql_text("0"))
    delivery_address: Mapped[str] = mapped_column(Text(), nullable=False, server_default=sql_text("''"))
    delivery_status: Mapped[str] = mapped_column(String(128), nullable=False, server_default=sql_text("''"))

    shop: Mapped["ShopModel"] = relationship("ShopModel", back_populates="orders")
    items: Mapped[list["OrderItemModel"]] = relationship(
        "OrderItemModel",
        back_populates="order",
        cascade="all, delete-orphan",
    )


class OrderItemModel(Base):
    """Позиция заказа."""

    __tablename__ = "shop_order_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sql_text("gen_random_uuid()"),
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shop_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shop_products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    quantity: Mapped[int] = mapped_column(Integer(), nullable=False)
    price_at_time: Mapped[Any] = mapped_column(Numeric(12, 2), nullable=False)

    order: Mapped["OrderModel"] = relationship("OrderModel", back_populates="items")


class StaticPageModel(Base):
    """Статическая страница витрины (контент по slug)."""

    __tablename__ = "shop_static_pages"
    __table_args__ = (UniqueConstraint("shop_id", "slug", name="uq_shop_static_pages_shop_slug"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sql_text("gen_random_uuid()"),
    )
    shop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shops.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    slug: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text(), nullable=False, server_default=sql_text("''"))

    shop: Mapped["ShopModel"] = relationship("ShopModel", back_populates="static_pages")


class MedicalEntryType(str, enum.Enum):
    """Тип записи МИС: обследование или опросник."""

    exam = "exam"
    survey = "survey"


class MedicalDoctorModel(Base):
    """Врач МИС: привязка к организации и учётной записи портала."""

    __tablename__ = "medical_doctors"
    __table_args__ = (UniqueConstraint("portal_user_id", name="uq_medical_doctors_portal_user"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sql_text("gen_random_uuid()"),
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    portal_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("portal_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    qualification: Mapped[str] = mapped_column(Text(), nullable=False, server_default=sql_text("''"))
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

    organization: Mapped["OrganizationModel"] = relationship(
        "OrganizationModel",
        back_populates="medical_doctors",
    )
    portal_user: Mapped["PortalUserModel"] = relationship(
        "PortalUserModel",
        back_populates="medical_doctor_profile",
    )
    patients: Mapped[list["MedicalPatientModel"]] = relationship(
        "MedicalPatientModel",
        back_populates="doctor",
    )


class MedicalPatientModel(Base):
    """Карта пациента МИС."""

    __tablename__ = "medical_patients"
    __table_args__ = (
        Index(
            "uq_medical_patients_org_phone_nonempty",
            "organization_id",
            "phone",
            unique=True,
            postgresql_where=sql_text("phone IS NOT NULL AND trim(phone) <> ''"),
        ),
        Index(
            "uq_medical_patients_org_max_user_id_nonempty",
            "organization_id",
            "max_user_id",
            unique=True,
            postgresql_where=sql_text("max_user_id IS NOT NULL AND trim(max_user_id) <> ''"),
        ),
        Index(
            "uq_medical_patients_org_max_chat_id_nonempty",
            "organization_id",
            "max_chat_id",
            unique=True,
            postgresql_where=sql_text("max_chat_id IS NOT NULL AND trim(max_chat_id) <> ''"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sql_text("gen_random_uuid()"),
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("medical_doctors.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    full_name: Mapped[str] = mapped_column(String(512), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    max_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    max_chat_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    tg_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    vk_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    is_verified: Mapped[bool] = mapped_column(
        Boolean(),
        nullable=False,
        server_default=sql_text("false"),
    )
    birth_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    gender: Mapped[str | None] = mapped_column(String(32), nullable=True)
    height: Mapped[float | None] = mapped_column(Float(), nullable=True)
    weight: Mapped[float | None] = mapped_column(Float(), nullable=True)
    current_diagnosis: Mapped[str] = mapped_column(Text(), nullable=False, server_default=sql_text("''"))
    treatment_plan: Mapped[str] = mapped_column(Text(), nullable=False, server_default=sql_text("''"))
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

    organization: Mapped["OrganizationModel"] = relationship(
        "OrganizationModel",
        back_populates="medical_patients",
    )
    doctor: Mapped["MedicalDoctorModel"] = relationship(
        "MedicalDoctorModel",
        back_populates="patients",
    )
    entries: Mapped[list["MedicalEntryModel"]] = relationship(
        "MedicalEntryModel",
        back_populates="patient",
        cascade="all, delete-orphan",
    )


class MedicalEntryModel(Base):
    """Обследование или опросник: показатели и ответы в JSON."""

    __tablename__ = "medical_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sql_text("gen_random_uuid()"),
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("medical_patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[MedicalEntryType] = mapped_column(
        SQLEnum(MedicalEntryType, name="medical_entry_type", native_enum=True, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    entry_date: Mapped[date] = mapped_column(Date(), nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=sql_text("'{}'::jsonb"))
    conclusion: Mapped[str] = mapped_column(Text(), nullable=False, server_default=sql_text("''"))
    recommendations: Mapped[str] = mapped_column(Text(), nullable=False, server_default=sql_text("''"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sql_text("now()"),
        nullable=False,
    )

    patient: Mapped["MedicalPatientModel"] = relationship(
        "MedicalPatientModel",
        back_populates="entries",
    )


class MiniAppUserModel(Base):
    """Пользователь Mini App (мессенджер MAX): идентифицируется chat_id в рамках организации.

    Создаётся при первом входе в Web App организации по ссылке ``/inn/<inn>``: бэкенд
    извлекает chat_id из init_data мессенджера и upsert'ит запись по (organization_id, chat_id).
    """

    __tablename__ = "mini_app_users"
    __table_args__ = (
        UniqueConstraint("organization_id", "chat_id", name="uq_mini_app_users_org_chat"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sql_text("gen_random_uuid()"),
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chat_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
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

    organization: Mapped["OrganizationModel"] = relationship("OrganizationModel")


class SiteModel(Base):
    """Сайт Mini App: контейнер многостраничного контента, изолирован по организации.

    Настройки (title, subtitle, цвет, логотип, контакты) переиспользуются клиентским
    Mini App для шапки и подвала; контент — в ``SitePageModel``.
    """

    __tablename__ = "sites"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sql_text("gen_random_uuid()"),
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # standard — обычный сайт Mini App; mis — тот же конструктор, но сценарий МИС (роли врач/пациент).
    site_kind: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=sql_text("'standard'"),
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False, server_default=sql_text("''"))
    subtitle: Mapped[str] = mapped_column(String(512), nullable=False, server_default=sql_text("''"))
    logo_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    theme_color: Mapped[str] = mapped_column(String(16), nullable=False, server_default=sql_text("'#000000'"))
    contacts: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sql_text("'{}'::jsonb"),
    )
    # Пункты нижнего меню Mini App: [{ "id", "label", "page_id", "order_index", "is_visible" }, …]
    menu_items: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sql_text("'[]'::jsonb"),
    )
    #: Нижнее меню Mini App для МИС (site_kind=mis): отдельно «врач» и «пациент».
    mis_menu_items_doctor: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sql_text("'[]'::jsonb"),
    )
    mis_menu_items_patient: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sql_text("'[]'::jsonb"),
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

    # Явно указываем foreign_keys: у OrganizationModel теперь два FK к/от sites
    # (organizations.active_site_id -> sites.id и sites.organization_id -> organizations.id),
    # поэтому SQLAlchemy иначе не может однозначно вывести join-условие.
    organization: Mapped["OrganizationModel"] = relationship(
        "OrganizationModel",
        foreign_keys=[organization_id],
    )
    pages: Mapped[list["SitePageModel"]] = relationship(
        "SitePageModel",
        back_populates="site",
        cascade="all, delete-orphan",
        order_by="SitePageModel.order_index.asc()",
    )


class DocumentModel(Base):
    """Текст для модуля «Читатель» (Библия и др.): загрузка и разбор на иерархию узлов."""

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sql_text("gen_random_uuid()"),
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    author: Mapped[str | None] = mapped_column(String(512), nullable=True)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
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

    organization: Mapped["OrganizationModel"] = relationship("OrganizationModel")
    nodes: Mapped[list["DocumentNodeModel"]] = relationship(
        "DocumentNodeModel",
        back_populates="document",
        cascade="all, delete-orphan",
    )
    linked_pages: Mapped[list["SitePageModel"]] = relationship(
        "SitePageModel",
        back_populates="linked_document",
    )


class DocumentNodeModel(Base):
    """Узел дерева документа: книга → глава → стих (или произвольный текст)."""

    __tablename__ = "document_nodes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sql_text("gen_random_uuid()"),
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_nodes.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    content: Mapped[str | None] = mapped_column(Text(), nullable=True)
    #: ``book`` | ``chapter`` | ``verse`` | ``text``
    node_type: Mapped[str] = mapped_column(String(16), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer(), nullable=False, server_default=sql_text("0"))

    document: Mapped["DocumentModel"] = relationship("DocumentModel", back_populates="nodes")
    parent: Mapped["DocumentNodeModel | None"] = relationship(
        "DocumentNodeModel",
        remote_side=[id],
        back_populates="children",
    )
    children: Mapped[list["DocumentNodeModel"]] = relationship(
        "DocumentNodeModel",
        back_populates="parent",
        cascade="all, delete-orphan",
    )


class SitePageModel(Base):
    """Страница сайта Mini App: slug уникален в рамках сайта."""

    __tablename__ = "site_pages"
    __table_args__ = (
        UniqueConstraint("site_id", "slug", name="uq_site_pages_site_slug"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sql_text("gen_random_uuid()"),
    )
    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    #: ``content`` — HTML из редактора; ``booking`` — в Mini App рендерится виджет записи к сотруднику.
    page_kind: Mapped[str] = mapped_column(String(32), nullable=False, server_default=sql_text("'content'"))
    #: Для МИС-сайта: ``doctor`` / ``patient`` — кому показывать страницу в Mini App.
    mis_audience: Mapped[str | None] = mapped_column(String(16), nullable=True)
    #: Сотрудник (portal_users), к чьему расписанию привязана страница; только при ``page_kind == booking``.
    booking_staff_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("portal_users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    #: Встроенный модуль платформы (заглушка до отдельной реализации UI).
    embed_module: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    #: Страница ``page_kind=document_reader`` — связь с загруженным текстом «Читатель».
    linked_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    content: Mapped[str] = mapped_column(Text(), nullable=False, server_default=sql_text("''"))
    order_index: Mapped[int] = mapped_column(Integer(), nullable=False, server_default=sql_text("0"))
    is_published: Mapped[bool] = mapped_column(Boolean(), nullable=False, server_default=sql_text("true"))
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

    site: Mapped["SiteModel"] = relationship("SiteModel", back_populates="pages")
    linked_document: Mapped["DocumentModel | None"] = relationship(
        "DocumentModel",
        back_populates="linked_pages",
    )


class BookingConfigModel(Base):
    """Настройки онлайн-записи к сотруднику (рабочие часы, длительность приёма)."""

    __tablename__ = "booking_configs"
    __table_args__ = (UniqueConstraint("portal_user_id", "organization_id", name="uq_booking_configs_user_org"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sql_text("gen_random_uuid()"),
    )
    portal_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("portal_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    working_hours: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sql_text("'{}'::jsonb"),
    )
    appointment_duration: Mapped[int] = mapped_column(Integer(), nullable=False, server_default=sql_text("30"))
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

    portal_user: Mapped["PortalUserModel"] = relationship("PortalUserModel")
    organization: Mapped["OrganizationModel"] = relationship("OrganizationModel")


class BusySlotModel(Base):
    """Разовая блокировка интервала (недоступно для записи)."""

    __tablename__ = "booking_busy_slots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sql_text("gen_random_uuid()"),
    )
    portal_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("portal_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(512), nullable=False, server_default=sql_text("''"))

    portal_user: Mapped["PortalUserModel"] = relationship("PortalUserModel")


class AppointmentModel(Base):
    """Запись клиента к сотруднику."""

    __tablename__ = "booking_appointments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sql_text("gen_random_uuid()"),
    )
    portal_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("portal_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_info: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sql_text("'{}'::jsonb"),
    )
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default=sql_text("'pending'"))
    service_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
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

    portal_user: Mapped["PortalUserModel"] = relationship("PortalUserModel")
    organization: Mapped["OrganizationModel"] = relationship("OrganizationModel")


class LegalOrgType(enum.Enum):
    """ОПФ организации для модуля «Комплаенс»."""

    OOO = "OOO"
    AO = "AO"
    IP = "IP"
    NKO = "NKO"


class LegalTaxSystem(enum.Enum):
    """Система налогообложения."""

    OSNO = "OSNO"
    USN_INCOME = "USN_INCOME"
    USN_INCOME_EXPENSE = "USN_INCOME_EXPENSE"
    PATENT = "PATENT"


class ComplianceDeadlineStatus(enum.Enum):
    """Статус контрольного срока."""

    PENDING = "pending"
    COMPLETED = "completed"
    OVERDUE = "overdue"


class LegalDocType(enum.Enum):
    """Тип юридического документа."""

    PROTOCOL = "protocol"
    REPORT = "report"
    CONTRACT = "contract"
    OTHER = "other"


class LegalDocStatus(enum.Enum):
    """Статус редакции документа."""

    DRAFT = "draft"
    FINAL = "final"
    SIGNED = "signed"


class LegalProfileModel(Base):
    """Профиль организации для комплаенса (устав, ОПФ, налоговый режим)."""

    __tablename__ = "legal_profiles"
    __table_args__ = (UniqueConstraint("organization_id", name="uq_legal_profiles_organization"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sql_text("gen_random_uuid()"),
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    org_type: Mapped[LegalOrgType] = mapped_column(
        SQLEnum(LegalOrgType, name="legal_org_type_str", native_enum=False, length=16),
        nullable=False,
    )
    tax_system: Mapped[LegalTaxSystem] = mapped_column(
        SQLEnum(LegalTaxSystem, name="legal_tax_system_str", native_enum=False, length=24),
        nullable=False,
    )
    general_director_name: Mapped[str] = mapped_column(String(512), nullable=False, server_default=sql_text("''"))
    charter_rules: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sql_text("'{}'::jsonb"),
    )
    #: Идентификатор роли из **SYSTEM_ROLES_CONFIG** (строка, как в JSON ``roles[].id``).
    system_role_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    #: UUID элементов базы знаний организации (устав, протоколы и т.д.) — контекст для генерации.
    knowledge_item_ids: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sql_text("'[]'::jsonb"),
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

    organization: Mapped["OrganizationModel"] = relationship("OrganizationModel")


class ComplianceDeadlineModel(Base):
    """Контрольные сроки отчётности и секретариата."""

    __tablename__ = "compliance_deadlines"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sql_text("gen_random_uuid()"),
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    due_date: Mapped[date] = mapped_column(Date(), nullable=False, index=True)
    status: Mapped[ComplianceDeadlineStatus] = mapped_column(
        SQLEnum(ComplianceDeadlineStatus, name="compliance_deadline_status_str", native_enum=False, length=16),
        nullable=False,
        server_default=sql_text("'pending'"),
    )
    description: Mapped[str] = mapped_column(Text(), nullable=False, server_default=sql_text("''"))

    organization: Mapped["OrganizationModel"] = relationship("OrganizationModel")


class LegalDocumentModel(Base):
    """Протоколы, отчёты и иные текстовые юридические документы."""

    __tablename__ = "legal_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sql_text("gen_random_uuid()"),
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    doc_type: Mapped[LegalDocType] = mapped_column(
        SQLEnum(LegalDocType, name="legal_doc_type_str", native_enum=False, length=16),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text(), nullable=False, server_default=sql_text("''"))
    status: Mapped[LegalDocStatus] = mapped_column(
        SQLEnum(LegalDocStatus, name="legal_doc_status_str", native_enum=False, length=16),
        nullable=False,
        server_default=sql_text("'draft'"),
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

    organization: Mapped["OrganizationModel"] = relationship("OrganizationModel")
