"""Pydantic-схемы HTTP для лидов."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class LeadStatusSchema(str, Enum):
    """Допустимые значения статуса в HTTP API (согласованы с доменным LeadStatus)."""

    NEW = "new"
    IN_PROGRESS = "in_progress"
    QUALIFIED = "qualified"


class LeadCreateRequest(BaseModel):
    """Тело запроса на создание лида."""

    name: str = Field(..., min_length=1, max_length=255)
    phone_number: str = Field(..., min_length=1, max_length=64)
    status: LeadStatusSchema | None = Field(
        default=None,
        description="Если не указан, используется статус «new»",
    )


class LeadResponse(BaseModel):
    """Ответ с созданным лидом."""

    id: UUID
    name: str
    phone_number: str
    status: LeadStatusSchema
    created_at: datetime

    model_config = {"from_attributes": True}
