"""Доменная модель универсальной интеграции с внешними API (JSONB в PostgreSQL)."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Literal, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, SecretStr


class AuthType(str, Enum):
    """Способ аутентификации исходящих запросов к внешней системе."""

    NO_AUTH = "NO_AUTH"
    BEARER = "BEARER"
    API_KEY = "API_KEY"
    BASIC = "BASIC"


class NoAuthConfig(BaseModel):
    """Без аутентификации (публичные или внутренние endpoint'ы)."""

    model_config = ConfigDict(extra="forbid")

    auth_type: Literal[AuthType.NO_AUTH] = Field(
        default=AuthType.NO_AUTH,
        description="Дискриминатор: запросы без заголовков авторизации.",
    )


class BearerAuthConfig(BaseModel):
    """Authorization: Bearer <token>."""

    model_config = ConfigDict(extra="forbid")

    auth_type: Literal[AuthType.BEARER] = Field(
        default=AuthType.BEARER,
        description="Дискриминатор: Bearer-токен.",
    )
    token: SecretStr = Field(description="Секретный Bearer-токен (не логировать в открытом виде).")


class ApiKeyAuthConfig(BaseModel):
    """API-ключ в произвольном HTTP-заголовке (например X-Api-Key)."""

    model_config = ConfigDict(extra="forbid")

    auth_type: Literal[AuthType.API_KEY] = Field(
        default=AuthType.API_KEY,
        description="Дискриминатор: ключ в именованном заголовке.",
    )
    header_name: str = Field(
        min_length=1,
        max_length=128,
        description="Имя HTTP-заголовка для передачи ключа.",
    )
    header_value: SecretStr = Field(description="Значение API-ключа.")


class BasicAuthConfig(BaseModel):
    """HTTP Basic: логин и пароль."""

    model_config = ConfigDict(extra="forbid")

    auth_type: Literal[AuthType.BASIC] = Field(
        default=AuthType.BASIC,
        description="Дискриминатор: Basic Auth.",
    )
    username: str = Field(min_length=1, max_length=256, description="Имя пользователя Basic.")
    password: SecretStr = Field(description="Пароль Basic (секрет).")


AuthConfig = Annotated[
    Union[NoAuthConfig, BearerAuthConfig, ApiKeyAuthConfig, BasicAuthConfig],
    Field(discriminator="auth_type"),
]


class ActionParamType(str, Enum):
    """Тип параметра действия (для схемы входа и LLM tool)."""

    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    OBJECT = "object"
    ARRAY = "array"


class ActionParameter(BaseModel):
    """Описание входного параметра действия (path/query/body)."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[a-zA-Z0-9_]+$",
        description="Имя параметра (латиница, цифры, подчёркивание).",
    )
    type: ActionParamType = Field(description="Тип значения для валидации и подсказок LLM.")
    description: str = Field(
        min_length=1,
        max_length=2000,
        description="Человекочитаемое описание параметра.",
    )
    required: bool = Field(default=True, description="Обязателен ли параметр при вызове.")


HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE"]


class IntegrationAction(BaseModel):
    """Исходящий HTTP-вызов к внешней системе (инструмент агента или внутренняя задача)."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="Уникальный идентификатор действия для кода и LLM (a-z, A-Z, 0-9, _, -).",
    )
    description: str = Field(min_length=1, max_length=4000, description="Назначение действия.")
    method: HttpMethod = Field(description="HTTP-метод запроса.")
    path: str = Field(
        min_length=1,
        max_length=2048,
        description="Относительный путь, например /v1/orders/{id}.",
    )
    parameters: list[ActionParameter] = Field(
        default_factory=list,
        description="Схема входных параметров.",
    )
    is_llm_tool: bool = Field(
        default=True,
        description="Если True — действие доступно LLM как tool; если False — только для системы (Celery и т.д.).",
    )


class IncomingWebhook(BaseModel):
    """Входящий вебхук: мы отдаём внешней системе URL с суффиксом."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        min_length=1,
        max_length=128,
        description="Системное имя события, например on_new_lead.",
    )
    description: str = Field(
        min_length=1,
        max_length=2000,
        description="Какое событие во внешней системе инициирует вызов.",
    )
    path_suffix: str = Field(
        min_length=1,
        max_length=256,
        description="Уникальный суффикс URL для приёма payload (генерируется платформой).",
    )
    is_active: bool = Field(default=True, description="Принимать ли запросы на этот endpoint.")


class Integration(BaseModel):
    """Агрегат конфигурации интеграции с внешним API."""

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(description="Идентификатор записи в хранилище.")
    name: str = Field(min_length=1, max_length=256, description="Отображаемое имя интеграции.")
    base_url: HttpUrl = Field(description="Базовый URL API внешней системы (http/https).")
    auth: AuthConfig = Field(description="Конфигурация аутентификации (полиморфная по auth_type).")
    actions: list[IntegrationAction] = Field(
        default_factory=list,
        description="Исходящие действия (REST-вызовы).",
    )
    webhooks: list[IncomingWebhook] = Field(
        default_factory=list,
        description="Входящие вебхуки, которые мы публикуем.",
    )
    created_at: datetime = Field(description="Момент создания записи.")
    updated_at: datetime = Field(description="Момент последнего обновления конфигурации.")
