"""Доменные сущности отдела продаж и базы знаний (промышленное оборудование)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID


class LeadStatus(str, Enum):
    """Стадия лида в воронке."""

    NEW = "new"
    IN_PROGRESS = "in_progress"
    QUALIFIED = "qualified"


class CallDirection(str, Enum):
    """Направление вызова (SIP или веб)."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"
    WEB = "web"


class DialerQueueStatus(str, Enum):
    """Статус записи в очереди автообзвона."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class Lead:
    """Лид — клиент, заинтересованный в промышленном оборудовании."""

    name: str
    phone_number: str
    status: LeadStatus
    id: UUID | None = None
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class CallRecord:
    """Запись о завершённой сессии (голос/текст/SIP) для CRM и ОКК."""

    session_id: str
    duration: int
    status: str
    transcript_text: str
    direction: str = CallDirection.WEB.value
    remote_phone: str = ""
    id: UUID | None = None
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class CallAnalytics:
    """Результат анализа диалога отделом контроля качества (LLM)."""

    call_record_id: UUID
    score: int
    recommendations: str
    id: UUID | None = None
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class DialerQueueItem:
    """Номер в очереди исходящего обзвона (Celery + SIP)."""

    phone: str
    status: DialerQueueStatus
    scheduled_at: datetime
    id: UUID | None = None
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class TrainingScenario:
    """Сценарий тренажёра: персона ИИ-клиента и возражения для отработки менеджером."""

    title: str
    client_persona_prompt: str
    objections_to_raise: str
    id: UUID | None = None
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class TrainingSession:
    """Результат тренировочного звонка: оценка тренера (LLM) по работе менеджера."""

    scenario_id: UUID
    manager_name: str
    session_id: str
    score: int
    feedback_text: str
    id: UUID | None = None
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class SystemSetting:
    """Параметр системы, редактируемый руководителем из панели (LLM, промпты, токены)."""

    key: str
    value: str
    description: str
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class KnowledgeItem:
    """Элемент базы знаний (прайсы, описания для RAG). Вектор заполняется позже пайплайном эмбеддингов."""

    title: str
    content: str
    id: UUID | None = None
    embedding: list[float] | None = None
