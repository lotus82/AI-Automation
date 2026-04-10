"""Зависимости FastAPI: репозиторий интеграций и сценарий выполнения действия."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import SettingsDep
from src.application.use_cases.execute_action import ExecuteActionUseCase
from src.domain.interfaces.repositories.integration_repo import IIntegrationRepository
from src.infrastructure.database import get_async_session
from src.infrastructure.providers.httpx_api_provider import HttpxAPIProvider
from src.infrastructure.repositories import SqlAlchemyIntegrationRepository
from src.infrastructure.security.encryption import SymmetricEncryption

# Алиас для согласованности с типовыми именами из ТЗ (get_db_session).
get_db_session = get_async_session


def get_encryption_service(settings: SettingsDep) -> SymmetricEncryption:
    """Fernet-ключ из настроек окружения (``INTEGRATION_FERNET_KEY``)."""
    key = (settings.integration_fernet_key or "").strip()
    if not key:
        raise HTTPException(
            status_code=503,
            detail="Интеграции недоступны: задайте INTEGRATION_FERNET_KEY в окружении.",
        )
    return SymmetricEncryption(key)


def get_integration_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    encryption: Annotated[SymmetricEncryption, Depends(get_encryption_service)],
) -> IIntegrationRepository:
    return SqlAlchemyIntegrationRepository(session, encryption)


def get_http_api_provider() -> HttpxAPIProvider:
    return HttpxAPIProvider()


def get_execute_action_use_case(
    repo: Annotated[IIntegrationRepository, Depends(get_integration_repository)],
    api_provider: Annotated[HttpxAPIProvider, Depends(get_http_api_provider)],
) -> ExecuteActionUseCase:
    return ExecuteActionUseCase(repo, api_provider)


IntegrationRepositoryDep = Annotated[IIntegrationRepository, Depends(get_integration_repository)]
ExecuteActionUseCaseDep = Annotated[ExecuteActionUseCase, Depends(get_execute_action_use_case)]
