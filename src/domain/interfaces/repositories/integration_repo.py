"""Репозиторий агрегата Integration (реализация — в infrastructure)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.entities.integration import Integration


class IIntegrationRepository(ABC):
    """Персистентность конфигураций интеграций с внешними системами."""

    @abstractmethod
    async def create(self, entity: Integration) -> Integration:
        """Сохранить новую интеграцию и вернуть сущность (например с тем же id)."""

    @abstractmethod
    async def get_by_id(self, integration_id: UUID) -> Integration:
        """Вернуть интеграцию по id или поднять ``IntegrationNotFoundError``."""

    @abstractmethod
    async def update(self, entity: Integration) -> Integration:
        """Обновить существующую интеграцию (полная замена или merge — на усмотрение реализации)."""

    @abstractmethod
    async def delete(self, integration_id: UUID) -> None:
        """Удалить интеграцию по id."""

    @abstractmethod
    async def list_all(self) -> list[Integration]:
        """Список всех интеграций (порядок — на усмотрение реализации)."""
