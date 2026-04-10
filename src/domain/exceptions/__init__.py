"""Доменные исключения (нарушения бизнес-правил)."""

from src.domain.exceptions.integration_exceptions import (
    ActionNotFoundError,
    IntegrationCallError,
    IntegrationNotFoundError,
)


class DomainValidationError(ValueError):
    """Нарушение доменных правил валидации (для маппинга в HTTP 422)."""


__all__ = [
    "ActionNotFoundError",
    "DomainValidationError",
    "IntegrationCallError",
    "IntegrationNotFoundError",
]
