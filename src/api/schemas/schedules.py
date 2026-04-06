"""Схемы API расписаний (фаза 18)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from src.domain.entities import ScheduleType


class ScheduleCreateBody(BaseModel):
    """Создание расписания из панели."""

    chat_id: str = Field(..., description="Числовой chat_id чата MAX")
    is_active: bool = True
    type: ScheduleType
    prompt: str = ""
    content_template: str = ""
    interval_settings: dict[str, Any] = Field(default_factory=dict)
    reminder_offset_minutes: int | None = None


class SchedulePatchBody(BaseModel):
    """Частичное обновление расписания (только переданные поля)."""

    chat_id: str | None = None
    is_active: bool | None = None
    type: ScheduleType | None = None
    prompt: str | None = None
    content_template: str | None = None
    interval_settings: dict[str, Any] | None = None
    reminder_offset_minutes: int | None = None


class ScheduleResponse(BaseModel):
    """Расписание в ответе API."""

    id: UUID
    chat_id: str
    is_active: bool
    type: ScheduleType
    prompt: str
    content_template: str
    interval_settings: dict[str, Any]
    reminder_offset_minutes: int | None
    last_run_at: datetime | None
    created_at: datetime | None


class ScheduleEventsUploadResult(BaseModel):
    """Результат импорта событий (CSV/JSON)."""

    imported: int
    errors: list[str] = Field(default_factory=list)
