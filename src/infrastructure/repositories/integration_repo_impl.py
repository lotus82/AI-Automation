"""Реализация ``IIntegrationRepository`` на SQLAlchemy async + шифрование секретов в JSONB."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.integration import (
    ApiKeyAuthConfig,
    AuthConfig,
    AuthType,
    BasicAuthConfig,
    BearerAuthConfig,
    Integration,
    NoAuthConfig,
)
from src.domain.exceptions.integration_exceptions import IntegrationNotFoundError
from src.domain.interfaces.repositories.integration_repo import IIntegrationRepository
from src.infrastructure.models import IntegrationModel
from src.infrastructure.security.encryption import SymmetricEncryption


def _auth_to_storage(auth: AuthConfig, enc: SymmetricEncryption) -> dict[str, Any]:
    """Сериализация auth в JSON с зашифрованными секретами."""
    if isinstance(auth, NoAuthConfig):
        return auth.model_dump(mode="json")
    if isinstance(auth, BearerAuthConfig):
        return {
            "auth_type": AuthType.BEARER.value,
            "token": enc.encrypt(auth.token.get_secret_value()),
        }
    if isinstance(auth, ApiKeyAuthConfig):
        return {
            "auth_type": AuthType.API_KEY.value,
            "header_name": auth.header_name,
            "header_value": enc.encrypt(auth.header_value.get_secret_value()),
        }
    if isinstance(auth, BasicAuthConfig):
        return {
            "auth_type": AuthType.BASIC.value,
            "username": auth.username,
            "password": enc.encrypt(auth.password.get_secret_value()),
        }
    raise TypeError(f"Unsupported auth config: {type(auth)!r}")


def _auth_from_storage(data: dict[str, Any], enc: SymmetricEncryption) -> AuthConfig:
    """Восстановление Pydantic-auth из JSON после расшифровки секретов."""
    raw_type = data.get("auth_type")
    if raw_type in (AuthType.NO_AUTH.value, "NO_AUTH"):
        return NoAuthConfig.model_validate(data)
    if raw_type in (AuthType.BEARER.value, "BEARER"):
        cipher = data["token"]
        plain = enc.decrypt(str(cipher))
        return BearerAuthConfig(token=SecretStr(plain))
    if raw_type in (AuthType.API_KEY.value, "API_KEY"):
        cipher = data["header_value"]
        plain = enc.decrypt(str(cipher))
        return ApiKeyAuthConfig(
            header_name=str(data["header_name"]),
            header_value=SecretStr(plain),
        )
    if raw_type in (AuthType.BASIC.value, "BASIC"):
        cipher = data["password"]
        plain = enc.decrypt(str(cipher))
        return BasicAuthConfig(
            username=str(data["username"]),
            password=SecretStr(plain),
        )
    raise ValueError(f"Unknown auth_type in stored config: {raw_type!r}")


class SqlAlchemyIntegrationRepository(IIntegrationRepository):
    """Хранение агрегата ``Integration`` в PostgreSQL (JSONB + Fernet для секретов auth)."""

    def __init__(self, session: AsyncSession, encryption: SymmetricEncryption) -> None:
        self._session = session
        self._encryption = encryption

    def _build_config_json(self, entity: Integration) -> dict[str, Any]:
        return {
            "auth": _auth_to_storage(entity.auth, self._encryption),
            "actions": [a.model_dump(mode="json") for a in entity.actions],
            "webhooks": [w.model_dump(mode="json") for w in entity.webhooks],
        }

    def _to_domain(self, model: IntegrationModel) -> Integration:
        cfg = dict(model.config) if model.config else {}
        auth_raw = cfg.get("auth") or {"auth_type": AuthType.NO_AUTH.value}
        return Integration.model_validate(
            {
                "id": model.id,
                "name": model.name,
                "base_url": model.base_url,
                "auth": _auth_from_storage(auth_raw, self._encryption),
                "actions": cfg.get("actions", []),
                "webhooks": cfg.get("webhooks", []),
                "created_at": model.created_at,
                "updated_at": model.updated_at,
            }
        )

    def _to_persistence(self, entity: Integration) -> IntegrationModel:
        return IntegrationModel(
            id=entity.id,
            name=entity.name,
            base_url=str(entity.base_url),
            config=self._build_config_json(entity),
        )

    async def create(self, entity: Integration) -> Integration:
        row = self._to_persistence(entity)
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return self._to_domain(row)

    async def get_by_id(self, integration_id: UUID) -> Integration:
        row = await self._session.get(IntegrationModel, integration_id)
        if row is None:
            raise IntegrationNotFoundError(str(integration_id))
        return self._to_domain(row)

    async def update(self, entity: Integration) -> Integration:
        row = await self._session.get(IntegrationModel, entity.id)
        if row is None:
            raise IntegrationNotFoundError(str(entity.id))
        row.name = entity.name
        row.base_url = str(entity.base_url)
        row.config = self._build_config_json(entity)
        await self._session.flush()
        await self._session.refresh(row)
        return self._to_domain(row)

    async def delete(self, integration_id: UUID) -> None:
        row = await self._session.get(IntegrationModel, integration_id)
        if row is None:
            raise IntegrationNotFoundError(str(integration_id))
        await self._session.delete(row)
        await self._session.flush()

    async def list_all(self) -> list[Integration]:
        stmt = select(IntegrationModel).order_by(IntegrationModel.created_at.desc())
        result = await self._session.scalars(stmt)
        return [self._to_domain(m) for m in result.all()]
