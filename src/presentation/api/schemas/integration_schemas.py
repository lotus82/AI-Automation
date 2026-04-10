"""Схемы REST для модуля интеграций (без утечки секретов в ответах)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, Field, HttpUrl, model_validator

from src.domain.entities.integration import (
    AuthConfig,
    AuthType,
    IncomingWebhook,
    Integration,
    IntegrationAction,
)

_AUTH_SECRET_MASK = "********"


def mask_auth_payload(auth: dict[str, Any]) -> dict[str, Any]:
    """Маскирует чувствительные поля в сериализованном ``auth`` (после ``model_dump``)."""
    if not isinstance(auth, dict):
        return auth
    out = dict(auth)
    at = out.get("auth_type")
    if at in (AuthType.BEARER.value, "BEARER"):
        if "token" in out:
            out["token"] = _AUTH_SECRET_MASK
    elif at in (AuthType.API_KEY.value, "API_KEY"):
        if "header_value" in out:
            out["header_value"] = _AUTH_SECRET_MASK
    elif at in (AuthType.BASIC.value, "BASIC"):
        if "password" in out:
            out["password"] = _AUTH_SECRET_MASK
    return out


class IntegrationCreateRequest(BaseModel):
    """Тело создания интеграции (идентификатор и метки времени выставляет сервер)."""

    name: Annotated[str, Field(min_length=1, max_length=256)]
    base_url: HttpUrl
    auth: AuthConfig
    actions: list[IntegrationAction] = Field(default_factory=list)
    webhooks: list[IncomingWebhook] = Field(default_factory=list)


class IntegrationUpdateRequest(BaseModel):
    """Полная замена конфигурации (PUT): те же поля, что при создании."""

    name: Annotated[str, Field(min_length=1, max_length=256)]
    base_url: HttpUrl
    auth: AuthConfig
    actions: list[IntegrationAction] = Field(default_factory=list)
    webhooks: list[IncomingWebhook] = Field(default_factory=list)


class IntegrationResponse(BaseModel):
    """Ответ API: секреты в ``auth`` всегда замаскированы."""

    id: UUID
    name: str
    base_url: AnyHttpUrl
    auth: dict[str, Any]
    actions: list[dict[str, Any]]
    webhooks: list[dict[str, Any]]
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def _mask_sensitive_auth(cls, data: Any) -> Any:
        if isinstance(data, Integration):
            payload = data.model_dump(mode="json")
            payload["auth"] = mask_auth_payload(payload["auth"])
            payload["actions"] = [a.model_dump(mode="json") for a in data.actions]
            payload["webhooks"] = [w.model_dump(mode="json") for w in data.webhooks]
            return payload
        if isinstance(data, dict):
            d = dict(data)
            if isinstance(d.get("auth"), dict):
                d["auth"] = mask_auth_payload(d["auth"])
            return d
        return data


class ActionExecutionRequest(BaseModel):
    """Вызов действия интеграции по имени."""

    action_name: Annotated[str, Field(min_length=1, max_length=128)]
    input_params: dict[str, Any] = Field(default_factory=dict)
