"""Схемы API модуля «Записи» (booking)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class BookingConfigOut(BaseModel):
    id: UUID | None = None
    working_hours: dict[str, Any] = Field(default_factory=dict)
    appointment_duration: int = 30


class BookingConfigUpsert(BaseModel):
    working_hours: dict[str, Any] = Field(default_factory=dict)
    appointment_duration: int = Field(ge=5, le=480, default=30)


class BusySlotOut(BaseModel):
    id: UUID
    start_time: datetime
    end_time: datetime
    reason: str

    model_config = {"from_attributes": True}


class BusySlotCreate(BaseModel):
    start_time: datetime
    end_time: datetime
    reason: str = Field(default="", max_length=512)


class AppointmentOut(BaseModel):
    id: UUID
    portal_user_id: UUID
    organization_id: UUID
    client_info: dict[str, Any]
    start_time: datetime
    end_time: datetime
    status: str
    service_price: float | None

    model_config = {"from_attributes": True}


class AppointmentCancelPatch(BaseModel):
    pass


class BookingStatsOut(BaseModel):
    period_from: date
    period_to: date
    counts_by_status: dict[str, int]
    completed_consultations: int
    revenue_total: float
    popular_hours: list[dict[str, Any]]  # [{ "hour": 9, "count": 3 }, ...]
    completed_by_day: list[dict[str, Any]]  # [{ "day": "2026-04-01", "count": 2 }]


class PublicSlotItem(BaseModel):
    start_time: datetime
    end_time: datetime


class PublicSlotsOut(BaseModel):
    date: date
    portal_user_id: UUID
    organization_id: UUID
    appointment_duration: int
    slots: list[PublicSlotItem]


class PublicAppointmentCreate(BaseModel):
    staff_user_id: UUID
    organization_id: UUID
    start_time: datetime
    end_time: datetime
    client_info: dict[str, Any] = Field(default_factory=dict)
