"""Внедрение зависимостей FastAPI: сессия БД, репозитории, сценарии использования."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings, get_settings
from src.infrastructure.database import get_async_session
from src.infrastructure.monitoring import get_chat_events_broadcaster
from src.infrastructure.repositories import (
    HybridChatMemoryRepository,
    PostgresSettingsRepository,
    RedisChatMemoryRepository,
    SqlAlchemyCallRecordRepository,
    SqlAlchemyChatSessionRepository,
    SqlAlchemyDialerQueueRepository,
    SqlAlchemyKnowledgeRepository,
    SqlAlchemyLeadRepository,
    SqlAlchemyTrainingScenarioRepository,
)
from src.infrastructure.services.bitrix24 import build_crm_service
from src.infrastructure.services.dynamic_llm import DynamicLLMService
from src.infrastructure.services.max_messenger import MaxMessengerClient
from src.infrastructure.services.openai_embedding import OpenAIEmbeddingService
from src.use_cases.chat import ProcessTextMessageUseCase
from src.use_cases.interfaces import (
    ICallRecordRepository,
    IChatMemoryRepository,
    IChatMonitoringPublisher,
    IChatSessionQueryRepository,
    ICRMService,
    IDialerQueueRepository,
    IEmbeddingService,
    IKnowledgeRepository,
    ILeadRepository,
    ILLMService,
    ISettingsRepository,
    ITrainingScenarioRepository,
)
from src.use_cases.leads import CreateLeadUseCase

AsyncSessionDep = Annotated[AsyncSession, Depends(get_async_session)]


def get_settings_dependency() -> Settings:
    """Настройки приложения для фабрик зависимостей."""
    return get_settings()


SettingsDep = Annotated[Settings, Depends(get_settings_dependency)]


def get_redis_client(request: Request) -> Redis:
    """Async Redis из состояния приложения (создаётся в lifespan)."""
    return request.app.state.redis


RedisDep = Annotated[Redis, Depends(get_redis_client)]


def get_lead_repository(session: AsyncSessionDep) -> ILeadRepository:
    """Фабрика репозитория лидов для запроса."""
    return SqlAlchemyLeadRepository(session)


LeadRepositoryDep = Annotated[ILeadRepository, Depends(get_lead_repository)]


def get_create_lead_use_case(repo: LeadRepositoryDep) -> CreateLeadUseCase:
    """Сценарий создания лида с внедрённым портом репозитория."""
    return CreateLeadUseCase(repo)


CreateLeadUseCaseDep = Annotated[CreateLeadUseCase, Depends(get_create_lead_use_case)]


def get_knowledge_repository(session: AsyncSessionDep) -> IKnowledgeRepository:
    """Репозиторий базы знаний (векторный поиск и сохранение)."""
    return SqlAlchemyKnowledgeRepository(session)


KnowledgeRepositoryDep = Annotated[IKnowledgeRepository, Depends(get_knowledge_repository)]


def get_settings_repository(session: AsyncSessionDep, redis: RedisDep) -> ISettingsRepository:
    """Динамические настройки (PostgreSQL + Redis-кэш при чтении)."""
    return PostgresSettingsRepository(session, redis)


SettingsRepositoryDep = Annotated[ISettingsRepository, Depends(get_settings_repository)]


def get_embedding_service(
    settings: SettingsDep,
    settings_repository: SettingsRepositoryDep,
) -> IEmbeddingService:
    """Сервис эмбеддингов: ключ **OPENAI_API_KEY** из настроек БД или из env."""
    return OpenAIEmbeddingService(settings=settings, settings_repo=settings_repository)


EmbeddingServiceDep = Annotated[IEmbeddingService, Depends(get_embedding_service)]


def get_llm_service(
    settings: SettingsDep,
    settings_repository: SettingsRepositoryDep,
) -> ILLMService:
    """LLM DeepSeek (по умолчанию) или OpenAI — из настроек панели."""
    return DynamicLLMService(settings=settings, settings_repo=settings_repository)


LLMServiceDep = Annotated[ILLMService, Depends(get_llm_service)]


def get_crm_service(settings: SettingsDep) -> ICRMService:
    """CRM (Bitrix24) или заглушка без вебхука."""
    return build_crm_service(settings.bitrix24_webhook_url)


CRMDep = Annotated[ICRMService, Depends(get_crm_service)]


def get_dialer_queue_repository(session: AsyncSessionDep) -> IDialerQueueRepository:
    """Очередь автообзвона."""
    return SqlAlchemyDialerQueueRepository(session)


DialerQueueRepositoryDep = Annotated[
    IDialerQueueRepository,
    Depends(get_dialer_queue_repository),
]


def get_training_scenario_repository(session: AsyncSessionDep) -> ITrainingScenarioRepository:
    """Репозиторий сценариев тренажёра."""
    return SqlAlchemyTrainingScenarioRepository(session)


TrainingScenarioRepositoryDep = Annotated[
    ITrainingScenarioRepository,
    Depends(get_training_scenario_repository),
]


def get_call_record_repository(session: AsyncSessionDep) -> ICallRecordRepository:
    """Репозиторий записей звонков и аналитики для дашборда."""
    return SqlAlchemyCallRecordRepository(session)


CallRecordRepositoryDep = Annotated[
    ICallRecordRepository,
    Depends(get_call_record_repository),
]


def get_chat_memory_repository(
    session: AsyncSessionDep,
    redis: RedisDep,
    settings: SettingsDep,
) -> IChatMemoryRepository:
    """Память: Redis (TTL) + PostgreSQL ``chat_messages``."""
    inner = RedisChatMemoryRepository(
        redis,
        ttl_seconds=settings.chat_memory_ttl_seconds,
    )
    return HybridChatMemoryRepository(inner, session)


ChatMemoryRepositoryDep = Annotated[
    IChatMemoryRepository,
    Depends(get_chat_memory_repository),
]


def get_chat_monitoring_publisher() -> IChatMonitoringPublisher:
    """Рассылка событий на WebSocket ``/api/ws/monitoring``."""
    return get_chat_events_broadcaster()


ChatMonitoringPublisherDep = Annotated[
    IChatMonitoringPublisher,
    Depends(get_chat_monitoring_publisher),
]


def get_chat_session_query_repository(
    session: AsyncSessionDep,
) -> IChatSessionQueryRepository:
    """Выборки сессий для панели «Боты»."""
    return SqlAlchemyChatSessionRepository(session)


ChatSessionQueryRepositoryDep = Annotated[
    IChatSessionQueryRepository,
    Depends(get_chat_session_query_repository),
]


def get_process_text_message_use_case(
    embedding_service: EmbeddingServiceDep,
    knowledge_repository: KnowledgeRepositoryDep,
    llm_service: LLMServiceDep,
    chat_memory: ChatMemoryRepositoryDep,
    crm_service: CRMDep,
    settings_repository: SettingsRepositoryDep,
    chat_monitoring: ChatMonitoringPublisherDep,
) -> ProcessTextMessageUseCase:
    """Сценарий текстового RAG с историей в Redis."""
    return ProcessTextMessageUseCase(
        embedding_service=embedding_service,
        knowledge_repository=knowledge_repository,
        llm_service=llm_service,
        chat_memory=chat_memory,
        crm_service=crm_service,
        settings_repository=settings_repository,
        chat_monitoring=chat_monitoring,
    )


ProcessTextMessageUseCaseDep = Annotated[
    ProcessTextMessageUseCase,
    Depends(get_process_text_message_use_case),
]


def get_max_messenger_client(
    settings_repo: SettingsRepositoryDep,
    settings: SettingsDep,
) -> MaxMessengerClient:
    """Клиент MAX Bot API; токен подставляется из БД при отправке."""
    return MaxMessengerClient(
        settings_repository=settings_repo,
        api_base_url=settings.max_api_base,
        platform_api_base_url=settings.max_platform_api_base,
        env_fallback_max_bot_token=settings.max_bot_token,
    )


def build_max_long_poll_stack(
    session: AsyncSession,
    redis: Redis,
    settings: Settings,
) -> tuple[ProcessTextMessageUseCase, MaxMessengerClient]:
    """Собирает сценарий текста и клиент MAX с **одним** ``PostgresSettingsRepository`` (долгоживущая сессия long poll)."""
    settings_repo = PostgresSettingsRepository(session, redis)
    use_case = ProcessTextMessageUseCase(
        embedding_service=OpenAIEmbeddingService(settings=settings, settings_repo=settings_repo),
        knowledge_repository=SqlAlchemyKnowledgeRepository(session),
        llm_service=DynamicLLMService(settings=settings, settings_repo=settings_repo),
        chat_memory=HybridChatMemoryRepository(
            RedisChatMemoryRepository(redis, ttl_seconds=settings.chat_memory_ttl_seconds),
            session,
        ),
        crm_service=build_crm_service(settings.bitrix24_webhook_url),
        settings_repository=settings_repo,
        chat_monitoring=get_chat_events_broadcaster(),
    )
    client = MaxMessengerClient(
        settings_repository=settings_repo,
        api_base_url=settings.max_api_base,
        platform_api_base_url=settings.max_platform_api_base,
        env_fallback_max_bot_token=settings.max_bot_token,
    )
    return use_case, client


MaxMessengerClientDep = Annotated[
    MaxMessengerClient,
    Depends(get_max_messenger_client),
]
