"""Внедрение зависимостей FastAPI: сессия БД, репозитории, сценарии использования."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

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
    SqlAlchemyBitrixPortalRepository,
    SqlAlchemyCallRecordRepository,
    SqlAlchemyChatSessionRepository,
    SqlAlchemyDialerQueueRepository,
    SqlAlchemyKnowledgeRepository,
    SqlAlchemyLeadRepository,
    SqlAlchemyTrainingScenarioRepository,
)
from src.infrastructure.services.bitrix24 import build_crm_service
from src.infrastructure.services.dynamic_llm import DynamicLLMService
from src.infrastructure.services.questionnaire_llm import QuestionnaireLLMService
from src.infrastructure.services.trainer_ai import TrainerAIService
from src.infrastructure.services.max_messenger import MaxMessengerClient
from src.infrastructure.services.openai_embedding import OpenAIEmbeddingService
from src.infrastructure.services.web_search import DuckDuckGoSearchService
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
    ISearchService,
    ISettingsRepository,
    ITrainingScenarioRepository,
)
from src.use_cases.leads import CreateLeadUseCase

AsyncSessionDep = Annotated[AsyncSession, Depends(get_async_session)]


def get_bitrix_portal_repository(session: AsyncSessionDep) -> SqlAlchemyBitrixPortalRepository:
    """Репозиторий порталов Bitrix24 (OAuth) для роутера установки и событий."""
    return SqlAlchemyBitrixPortalRepository(session)


BitrixPortalRepoDep = Annotated[SqlAlchemyBitrixPortalRepository, Depends(get_bitrix_portal_repository)]


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


def get_trainer_ai_service(
    settings: SettingsDep,
    settings_repository: SettingsRepositoryDep,
) -> TrainerAIService:
    """LLM-разбор транскриптов BANT/MEDDIC (те же ключи, что у консультанта)."""
    return TrainerAIService(settings=settings, settings_repo=settings_repository)


TrainerAIServiceDep = Annotated[TrainerAIService, Depends(get_trainer_ai_service)]


def get_questionnaire_llm_service(
    settings: SettingsDep,
    settings_repository: SettingsRepositoryDep,
) -> QuestionnaireLLMService:
    """ИИ-оценка опросников (те же ключи LLM, что у консультанта)."""
    return QuestionnaireLLMService(settings=settings, settings_repo=settings_repository)


QuestionnaireLLMServiceDep = Annotated[
    QuestionnaireLLMService,
    Depends(get_questionnaire_llm_service),
]


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


def get_web_search_service() -> ISearchService:
    """Веб-поиск для инструмента ``search_web`` (DuckDuckGo, без скрейпинга магазинов)."""
    return DuckDuckGoSearchService()


SearchServiceDep = Annotated[ISearchService, Depends(get_web_search_service)]


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


def build_process_text_message_use_case(
    session: AsyncSession,
    redis: Redis,
    settings: Settings,
    *,
    organization_id: UUID | None = None,
) -> ProcessTextMessageUseCase:
    """Сборка сценария RAG с областью ``organization_id`` (настройки и база знаний организации) или глобально при ``None``."""
    settings_repo = PostgresSettingsRepository(session, redis, organization_id=organization_id)
    return ProcessTextMessageUseCase(
        embedding_service=OpenAIEmbeddingService(settings=settings, settings_repo=settings_repo),
        knowledge_repository=SqlAlchemyKnowledgeRepository(session, organization_id=organization_id),
        llm_service=DynamicLLMService(settings=settings, settings_repo=settings_repo),
        chat_memory=HybridChatMemoryRepository(
            RedisChatMemoryRepository(redis, ttl_seconds=settings.chat_memory_ttl_seconds),
            session,
        ),
        crm_service=build_crm_service(settings.bitrix24_webhook_url),
        settings_repository=settings_repo,
        chat_monitoring=get_chat_events_broadcaster(),
        search_service=DuckDuckGoSearchService(),
        redis_client=redis,
        app_settings=settings,
    )


def get_process_text_message_use_case(
    session: AsyncSessionDep,
    redis: RedisDep,
    settings: SettingsDep,
) -> ProcessTextMessageUseCase:
    """Сценарий текстового RAG с историей в Redis (глобальные настройки и БЗ без привязки к организации)."""
    return build_process_text_message_use_case(session, redis, settings, organization_id=None)


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
    *,
    organization_id: UUID | None = None,
) -> tuple[ProcessTextMessageUseCase, MaxMessengerClient]:
    """Собирает сценарий текста и клиент MAX с **одним** ``PostgresSettingsRepository`` (долгоживущая сессия long poll).

    ``organization_id``: область настроек/БЗ (переменная окружения ``MAX_LONG_POLL_ORGANIZATION_ID``); ``None`` — глобальные настройки.
    """
    settings_repo = PostgresSettingsRepository(session, redis, organization_id=organization_id)
    use_case = build_process_text_message_use_case(session, redis, settings, organization_id=organization_id)
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
