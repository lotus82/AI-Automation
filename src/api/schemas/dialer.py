"""Схемы API автообзвона."""

from __future__ import annotations

from pydantic import BaseModel


class DialerUploadResponse(BaseModel):
    """Результат загрузки файла с номерами."""

    inserted: int


class DialerCampaignStartResponse(BaseModel):
    """Постановка кампании в Celery."""

    status: str
