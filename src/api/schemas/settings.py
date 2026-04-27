"""Схемы API динамических настроек."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SystemSettingPublic(BaseModel):
    """Одна настройка для ответа GET (секреты маскируются на уровне роутера)."""

    key: str
    value: str
    description: str
    updated_at: datetime | None = None


class SettingsUpdateRequest(BaseModel):
    """Пакетное обновление: только разрешённые ключи из **UPDATABLE_KEYS**."""

    values: dict[str, str] = Field(
        default_factory=dict,
        description="Словарь key → value (пустая строка допустима для очистки ключа)",
    )


class LlmModelsResponse(BaseModel):
    """Список идентификаторов моделей для селектора (GET **/api/settings/llm-models**)."""

    models: list[str] = Field(default_factory=list, description="id модели для chat/completions")
    source: str = Field(
        default="fallback",
        description="api — с сервера провайдера; fallback — статический список (нет ключа или ошибка сети)",
    )
