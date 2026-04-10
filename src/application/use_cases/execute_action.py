"""Выполнение зарегистрированного действия интеграции по id и имени."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from src.application.interfaces.providers.api_provider import IExternalAPIProvider
from src.domain.entities.integration import Integration, IntegrationAction
from src.domain.exceptions.integration_exceptions import ActionNotFoundError
from src.domain.interfaces.repositories.integration_repo import IIntegrationRepository


class ExecuteActionUseCase:
    """Загружает интеграцию, находит действие и делегирует HTTP провайдеру."""

    def __init__(
        self,
        integration_repo: IIntegrationRepository,
        api_provider: IExternalAPIProvider,
    ) -> None:
        self._integration_repo = integration_repo
        self._api_provider = api_provider

    async def execute(
        self,
        integration_id: UUID,
        action_name: str,
        input_params: dict[str, Any],
    ) -> dict[str, Any]:
        integration = await self._integration_repo.get_by_id(integration_id)

        action = _find_action(integration, action_name)
        if action is None:
            raise ActionNotFoundError(action_name)

        return await self._api_provider.execute(integration, action, input_params)

    async def execute_among_integrations(
        self,
        integrations: list[Integration],
        action_name: str,
        input_params: dict[str, Any],
    ) -> dict[str, Any]:
        """Выполнить действие по имени в первой интеграции из списка, где оно объявлено.

        Порядок ``integrations`` должен совпадать с порядком ``integration_ids`` у оркестратора,
        чтобы при коллизии имён действий выбиралась ожидаемая интеграция.
        """
        for integration in integrations:
            action = _find_action(integration, action_name)
            if action is not None:
                return await self._api_provider.execute(integration, action, input_params)
        raise ActionNotFoundError(action_name)


def _find_action(integration: Integration, action_name: str) -> IntegrationAction | None:
    for a in integration.actions:
        if a.name == action_name:
            return a
    return None
