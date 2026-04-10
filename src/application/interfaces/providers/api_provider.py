"""Порт выполнения HTTP-действий внешней интеграции."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from src.domain.entities.integration import Integration, IntegrationAction


class IExternalAPIProvider(ABC):
    """Исходящий HTTP-вызов по конфигурации интеграции и действия."""

    @abstractmethod
    async def execute(
        self,
        integration: Integration,
        action: IntegrationAction,
        input_params: dict[str, Any],
    ) -> dict[str, Any]:
        """Собрать URL, заголовки, query/body из ``input_params`` и вернуть распарсенный JSON-ответ."""
