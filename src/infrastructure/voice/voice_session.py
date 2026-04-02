"""Общий запуск голосового пайплайна (браузер WebSocket или Asterisk RTP)."""

from __future__ import annotations

from typing import Literal, cast
from uuid import UUID

from loguru import logger
from redis.asyncio import Redis

from src.core.config import Settings
from src.domain import system_setting_keys as sk
from src.domain.entities import TrainingScenario
from src.infrastructure.database import AsyncSessionLocal
from src.infrastructure.monitoring import get_chat_events_broadcaster
from src.infrastructure.repositories import (
    HybridChatMemoryRepository,
    PostgresSettingsRepository,
    RedisChatMemoryRepository,
    SqlAlchemyKnowledgeRepository,
    SqlAlchemyTrainingScenarioRepository,
)
from src.infrastructure.services.bitrix24 import build_crm_service
from src.infrastructure.services.dynamic_llm import DynamicLLMService
from src.infrastructure.services.openai_embedding import OpenAIEmbeddingService
from src.infrastructure.services.salute_auth import SaluteSpeechAuthManager
from src.infrastructure.training_session_redis import (
    encode_trainer_meta,
    trainer_session_redis_key,
)
from src.use_cases.chat import ProcessTextMessageUseCase
from src.use_cases.interfaces import IVoiceTransport

_VoiceModeLit = Literal["consultant", "trainer_client"]


async def load_salutespeech_auth_key(settings: Settings, redis: Redis) -> str:
    """Authorization Key SaluteSpeech: переменная окружения или **system_settings** (кэш Redis)."""
    env_key = (settings.salutespeech_auth_key or "").strip()
    if env_key:
        return env_key
    async with AsyncSessionLocal() as session:
        try:
            repo = PostgresSettingsRepository(session, redis)
            db_key = (await repo.get_value(sk.SALUTESPEECH_AUTH_KEY) or "").strip()
            await session.commit()
        except Exception:
            await session.rollback()
            raise
    return db_key


async def resolve_effective_voice_stt_provider(
    settings: Settings, redis: Redis
) -> tuple[str, str | None]:
    """Фактический STT: при отсутствии **DEEPGRAM_API_KEY** переключаемся на SaluteSpeech, если ключ Сбера задан.

    Возвращает ``(effective_stt, reason_to_close_ws)``; ``reason`` — ``None``, если можно запускать пайплайн.
    """
    salute = await load_salutespeech_auth_key(settings, redis)
    effective = settings.voice_stt_provider
    if effective == "deepgram" and not (settings.deepgram_api_key or "").strip():
        if salute:
            effective = "salutespeech"
        else:
            return settings.voice_stt_provider, "Не задан DEEPGRAM_API_KEY"
    if effective == "salutespeech" and not salute:
        return effective, (
            "Не задан ключ SaluteSpeech (SALUTESPEECH_AUTH_KEY или панель настроек)"
        )
    if settings.voice_tts_provider == "salutespeech" and not salute:
        return effective, (
            "Не задан ключ SaluteSpeech (SALUTESPEECH_AUTH_KEY или панель настроек)"
        )
    return effective, None


def _build_trainer_system_prompt(scenario: TrainingScenario) -> str:
    return (
        f"{scenario.client_persona_prompt.strip()}\n\n"
        f"Возражения и темы, которые нужно естественно поднимать в диалоге:\n"
        f"{scenario.objections_to_raise.strip()}\n\n"
        "Отвечай коротко, как в живом звонке. Не раскрывай, что ты ИИ."
    )


async def run_voice_pipeline_session(
    *,
    session_id: str,
    voice_transport: IVoiceTransport,
    redis: Redis,
    settings: Settings,
    voice_mode: _VoiceModeLit,
    training_scenario: TrainingScenario | None,
    voice_stt_provider_effective: str | None = None,
) -> None:
    """STT → RAG/тренажёр → TTS; в конце постановка analyze_conversation_task."""
    from src.infrastructure.voice.processor import VoicePipelineOrchestrator

    if voice_stt_provider_effective is not None:
        stt_eff = voice_stt_provider_effective
    else:
        stt_eff, gate_err = await resolve_effective_voice_stt_provider(settings, redis)
        if gate_err:
            raise ValueError(gate_err)

    trainer_system: str | None = (
        _build_trainer_system_prompt(training_scenario)
        if training_scenario is not None
        else None
    )

    async def on_final_transcript(text: str) -> str:
        async with AsyncSessionLocal() as session:
            try:
                knowledge = SqlAlchemyKnowledgeRepository(session)
                redis_memory = RedisChatMemoryRepository(
                    redis,
                    ttl_seconds=settings.chat_memory_ttl_seconds,
                )
                memory = HybridChatMemoryRepository(redis_memory, session)
                settings_repo = PostgresSettingsRepository(session, redis)
                embeddings = OpenAIEmbeddingService(settings=settings, settings_repo=settings_repo)
                llm = DynamicLLMService(settings=settings, settings_repo=settings_repo)
                crm = build_crm_service(settings.bitrix24_webhook_url)
                use_case = ProcessTextMessageUseCase(
                    embedding_service=embeddings,
                    knowledge_repository=knowledge,
                    llm_service=llm,
                    chat_memory=memory,
                    crm_service=crm,
                    settings_repository=settings_repo,
                    chat_monitoring=get_chat_events_broadcaster(),
                )
                if voice_mode == "trainer_client" and trainer_system:
                    reply = await use_case.execute(
                        text,
                        session_id,
                        system_prompt_override=trainer_system,
                        use_crm_tools=False,
                        skip_rag=True,
                    )
                else:
                    reply = await use_case.execute(text, session_id)
                await session.commit()
                return reply
            except Exception:
                await session.rollback()
                raise

    salute_auth: SaluteSpeechAuthManager | None = None
    salute_voice: str | None = None
    if stt_eff == "salutespeech" or settings.voice_tts_provider == "salutespeech":
        raw_key = await load_salutespeech_auth_key(settings, redis)
        async with AsyncSessionLocal() as session:
            try:
                repo = PostgresSettingsRepository(session, redis)
                raw_scope = (
                    (await repo.get_value(sk.SALUTESPEECH_SCOPE) or "").strip()
                    or (settings.salutespeech_scope or "SALUTE_SPEECH_PERS").strip()
                )
                raw_voice = (
                    (await repo.get_value(sk.SALUTESPEECH_VOICE) or "").strip()
                    or (settings.salutespeech_voice or "Ost_24000").strip()
                )
                await session.commit()
            except Exception:
                await session.rollback()
                raise
        if not raw_key:
            msg = (
                "SaluteSpeech: задайте SALUTESPEECH_AUTH_KEY в .env или ключ SALUTESPEECH_AUTH_KEY "
                "в панели настроек"
            )
            raise ValueError(msg)
        salute_auth = SaluteSpeechAuthManager(
            redis,
            authorization_key=raw_key,
            scope=raw_scope,
            oauth_url=settings.salutespeech_oauth_url,
            oauth_verify_ssl=settings.salutespeech_oauth_verify_ssl,
            oauth_retries=settings.salutespeech_oauth_retries,
            oauth_trust_env=settings.salutespeech_oauth_trust_env,
        )
        salute_voice = raw_voice

    orchestrator = VoicePipelineOrchestrator(settings)
    await orchestrator.run(
        voice_transport=voice_transport,
        on_final_transcript=on_final_transcript,
        voice_mode=cast(_VoiceModeLit, voice_mode),
        training_scenario=training_scenario,
        salute_auth=salute_auth,
        salutespeech_voice=salute_voice,
        voice_stt_provider_effective=stt_eff,
        recording_session_id=session_id,
    )


def schedule_analyze_after_voice(session_id: str) -> None:
    """Вызывать из finally у роутера или ARI после остановки пайплайна."""
    try:
        from src.workers.tasks import analyze_conversation_task

        analyze_conversation_task.delay(session_id)
    except Exception:
        logger.exception(
            "Не удалось поставить в очередь analyze_conversation_task (session_id=%s)",
            session_id,
        )


async def load_training_scenario_for_voice(
    scenario_id: UUID,
) -> TrainingScenario | None:
    """Загрузка сценария тренажёра (общая логика с роутером /voice/stream)."""
    async with AsyncSessionLocal() as session:
        try:
            repo = SqlAlchemyTrainingScenarioRepository(session)
            sc = await repo.get_by_id(scenario_id)
            await session.commit()
            return sc
        except Exception:
            await session.rollback()
            raise


def trainer_meta_key(session_id: str) -> str:
    return trainer_session_redis_key(session_id)


def encode_trainer_redis_meta(*, scenario_id: str, manager_name: str) -> str:
    return encode_trainer_meta(scenario_id=scenario_id, manager_name=manager_name)
