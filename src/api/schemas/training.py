"""Схемы API тренажёра менеджеров."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TrainingScenarioCreate(BaseModel):
    """Создание сценария (РОП)."""

    title: str = Field(min_length=1, max_length=512)
    client_persona_prompt: str = Field(min_length=1)
    objections_to_raise: str = Field(min_length=1)


class TrainingScenarioResponse(BaseModel):
    """Сценарий в ответе API."""

    id: UUID
    title: str
    client_persona_prompt: str
    objections_to_raise: str
    created_at: datetime | None = None
