"""Схемы вебхуков SIP/PBX."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TelephonyInboundRequest(BaseModel):
    """Новый входящий вызов от АТС (Asterisk/FreeSWITCH и т.д.)."""

    call_id: str = Field(min_length=1, description="Уникальный id канала у PBX")
    caller_phone: str = Field(
        default="",
        description="Номер абонента (CLI), если известен",
    )


class TelephonyInboundResponse(BaseModel):
    """Ответ: session_id для привязки медиа-моста и записи в Redis."""

    session_id: str


TelephonyEventStatus = Literal["ringing", "answered", "hung_up"]


class TelephonyEventRequest(BaseModel):
    """Событие жизненного цикла вызова."""

    call_id: str = Field(min_length=1)
    status: TelephonyEventStatus
