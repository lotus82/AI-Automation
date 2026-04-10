"""Реализации репозиториев (async SQLAlchemy, Redis) и интеграций."""

from src.infrastructure.repositories.integration_repo_impl import SqlAlchemyIntegrationRepository
from src.infrastructure.repositories.stores import (
    HybridChatMemoryRepository,
    PostgresSettingsRepository,
    RedisChatMemoryRepository,
    SqlAlchemyBitrixPortalRepository,
    SqlAlchemyCallRecordRepository,
    SqlAlchemyChatSessionRepository,
    SqlAlchemyDialerQueueRepository,
    SqlAlchemyKnowledgeRepository,
    SqlAlchemyLeadRepository,
    SqlAlchemyScheduleRepository,
    SqlAlchemyTrainingScenarioRepository,
    SqlAlchemyTrainingSessionRepository,
)

__all__ = [
    "HybridChatMemoryRepository",
    "PostgresSettingsRepository",
    "RedisChatMemoryRepository",
    "SqlAlchemyBitrixPortalRepository",
    "SqlAlchemyCallRecordRepository",
    "SqlAlchemyChatSessionRepository",
    "SqlAlchemyDialerQueueRepository",
    "SqlAlchemyIntegrationRepository",
    "SqlAlchemyKnowledgeRepository",
    "SqlAlchemyLeadRepository",
    "SqlAlchemyScheduleRepository",
    "SqlAlchemyTrainingScenarioRepository",
    "SqlAlchemyTrainingSessionRepository",
]
