"""Схемы ответа API для записей звонков и ОКК."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CallAnalyticsItem(BaseModel):
    """Аналитика ОКК по одной записи."""

    id: UUID
    score: int = Field(ge=1, le=10)
    recommendations: str
    created_at: datetime | None = None


class CallRecordItem(BaseModel):
    """Запись сессии с опциональной аналитикой."""

    id: UUID
    session_id: str
    direction: str = "web"
    remote_phone: str = ""
    duration: int
    status: str
    transcript_text: str
    created_at: datetime | None = None
    analytics: CallAnalyticsItem | None = None


class CallsListResponse(BaseModel):
    """Список для фронтенда (Vanilla JS / fetch)."""

    items: list[CallRecordItem]
