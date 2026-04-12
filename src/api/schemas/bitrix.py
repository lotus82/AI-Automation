"""Pydantic-схемы Bitrix24 Marketplace (установка и вебхуки событий)."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from src.core.utils.bitrix import normalize_bitrix_portal_url


class BitrixInstallAuth(BaseModel):
    """Блок ``auth`` при установке приложения (вложенный объект или плоские поля формы)."""

    access_token: str = Field(..., min_length=1, description="OAuth access_token")
    refresh_token: str = Field(..., min_length=1, description="OAuth refresh_token")
    domain: str = Field(..., min_length=1, description="Домен портала, например foo.bitrix24.ru")
    member_id: str = Field(..., min_length=1, description="Уникальный идентификатор установки на портале")
    expires_in: int | None = Field(default=None, description="Срок жизни access_token в секундах")
    expires: int | None = Field(default=None, description="Unix-время истечения access_token")
    server_endpoint: str | None = None
    client_endpoint: str | None = None
    application_token: str | None = None

    @property
    def portal_url(self) -> str:
        return normalize_bitrix_portal_url(self.domain)


class BitrixInstallPayload(BaseModel):
    """Тело установки: JSON ``{"auth": {...}}`` или эквивалент из form-data."""

    auth: BitrixInstallAuth


class BitrixEventAuth(BaseModel):
    """Подполе ``auth`` во входящих событиях REST (ONCRMLEADADD и др.)."""

    domain: str = Field(..., min_length=1)
    application_token: str | None = Field(default=None, description="Секрет для сверки с BITRIX24_APPLICATION_TOKEN")
    member_id: str | None = None
    access_token: str | None = None

    @property
    def portal_url(self) -> str:
        return normalize_bitrix_portal_url(self.domain)


class BitrixWebhookPayload(BaseModel):
    """Входящее событие от Битрикс24 (типичный JSON вебхука приложения)."""

    event: str = Field(..., min_length=1, description="Имя события, например ONCRMLEADADD")
    data: dict[str, Any] = Field(default_factory=dict)
    auth: BitrixEventAuth
    ts: str | None = None

    @field_validator("data", mode="before")
    @classmethod
    def _data_dict(cls, v: Any) -> dict[str, Any]:
        if v is None:
            return {}
        if isinstance(v, dict):
            return v
        return {}


_AUTH_BRACKET_RE = re.compile(r"^auth\[([^\]]+)\]$", re.IGNORECASE)


def parse_bitrix_form_auth(flat: dict[str, str]) -> dict[str, str]:
    """Собирает словарь для ``BitrixInstallAuth`` из плоских ключей вида ``auth[access_token]`` и легаси AUTH_*."""
    auth: dict[str, str] = {}
    for raw_key, raw_val in flat.items():
        key = raw_key.strip()
        val = (raw_val or "").strip()
        if not val:
            continue
        m = _AUTH_BRACKET_RE.match(key)
        if m:
            inner = m.group(1).strip().lower().replace("-", "_")
            auth[inner] = val
            continue
        uk = key.upper()
        if uk in ("AUTH_ID", "ACCESS_TOKEN"):
            auth["access_token"] = val
        elif uk in ("REFRESH_ID", "REFRESH_TOKEN"):
            auth["refresh_token"] = val
        elif uk == "DOMAIN":
            auth["domain"] = val
        elif uk == "MEMBER_ID":
            auth["member_id"] = val
    return auth


def bitrix_install_from_flat_mapping(flat: dict[str, Any]) -> BitrixInstallPayload:
    """Разбор плоской формы или JSON с вложенным ``auth``."""
    if "auth" in flat and isinstance(flat["auth"], dict):
        return BitrixInstallPayload.model_validate(flat)
    # Плоский JSON без обёртки (все поля на верхнем уровне)
    if isinstance(flat.get("access_token"), str) and isinstance(flat.get("member_id"), str):
        return BitrixInstallPayload.model_validate({"auth": flat})
    auth_map = parse_bitrix_form_auth({str(k): str(v) for k, v in flat.items() if v is not None})
    if not auth_map:
        raise ValueError("Нет полей auth (ожидались auth[access_token] или JSON auth)")
    return BitrixInstallPayload.model_validate({"auth": auth_map})


class BitrixIndexForm(BaseModel):
    """Минимальные поля iframe-запроса (часто дублируют auth)."""

    DOMAIN: str | None = None
    AUTH_ID: str | None = None
    PLACEMENT: str | None = None

    @model_validator(mode="before")
    @classmethod
    def from_any(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return data
        return {}
