"""Реализации репозиториев (async SQLAlchemy, Redis) и интеграций."""

from src.infrastructure.repositories.compliance_repositories import (
    SqlAlchemyComplianceDeadlineRepository,
    SqlAlchemyLegalDocumentRepository,
    SqlAlchemyLegalProfileRepository,
)
from src.infrastructure.repositories.integration_repo_impl import SqlAlchemyIntegrationRepository
from src.infrastructure.repositories.shop_repositories import (
    SqlAlchemyCategoryRepository,
    SqlAlchemyDiscountRepository,
    SqlAlchemyShopOrderRepository,
    SqlAlchemyShopProductRepository,
    SqlAlchemyShopRepository,
    SqlAlchemyStaticPageRepository,
)
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
    "SqlAlchemyComplianceDeadlineRepository",
    "HybridChatMemoryRepository",
    "PostgresSettingsRepository",
    "RedisChatMemoryRepository",
    "SqlAlchemyBitrixPortalRepository",
    "SqlAlchemyCallRecordRepository",
    "SqlAlchemyCategoryRepository",
    "SqlAlchemyChatSessionRepository",
    "SqlAlchemyDialerQueueRepository",
    "SqlAlchemyLegalDocumentRepository",
    "SqlAlchemyLegalProfileRepository",
    "SqlAlchemyDiscountRepository",
    "SqlAlchemyIntegrationRepository",
    "SqlAlchemyKnowledgeRepository",
    "SqlAlchemyLeadRepository",
    "SqlAlchemyScheduleRepository",
    "SqlAlchemyShopOrderRepository",
    "SqlAlchemyShopProductRepository",
    "SqlAlchemyShopRepository",
    "SqlAlchemyStaticPageRepository",
    "SqlAlchemyTrainingScenarioRepository",
    "SqlAlchemyTrainingSessionRepository",
]
