"""Общий запуск голосового пайплайна (браузер WebSocket или Asterisk RTP)."""

from __future__ import annotations

from typing import Literal, cast
from uuid import UUID

from loguru import logger
from redis.asyncio import Redis

from src.core.config import Settings
from src.domain.entities import TrainingScenario
from src.infrastructure.database import AsyncSessionLocal
from src.infrastructure.repositories import (
    RedisChatMemoryRepository,
    SqlAlchemyKnowledgeRepository,
    SqlAlchemyTrainingScenarioRepository,
)
from src.infrastructure.services.bitrix24 import build_crm_service
from src.infrastructure.services.openai_embedding import OpenAIEmbeddingService
from src.infrastructure.services.openai_llm import OpenAILLMService
from src.infrastructure.training_session_redis import (
    encode_trainer_meta,
    trainer_session_redis_key,
)
from src.use_cases.chat import ProcessTextMessageUseCase
from src.use_cases.interfaces import IVoiceTransport

_VoiceModeLit = Literal["consultant", "trainer_client"]


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
) -> None:
    """STT → RAG/тренажёр → TTS; в конце постановка analyze_conversation_task."""
    from src.infrastructure.voice.processor import VoicePipelineOrchestrator

    trainer_system: str | None = (
        _build_trainer_system_prompt(training_scenario)
        if training_scenario is not None
        else None
    )

    async def on_final_transcript(text: str) -> str:
        async with AsyncSessionLocal() as session:
            try:
                knowledge = SqlAlchemyKnowledgeRepository(session)
                memory = RedisChatMemoryRepository(
                    redis,
                    ttl_seconds=settings.chat_memory_ttl_seconds,
                )
                embeddings = OpenAIEmbeddingService(settings=settings)
                llm = OpenAILLMService(settings=settings)
                crm = build_crm_service(settings.bitrix24_webhook_url)
                use_case = ProcessTextMessageUseCase(
                    embedding_service=embeddings,
                    knowledge_repository=knowledge,
                    llm_service=llm,
                    chat_memory=memory,
                    crm_service=crm,
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

    orchestrator = VoicePipelineOrchestrator(settings)
    await orchestrator.run(
        voice_transport=voice_transport,
        on_final_transcript=on_final_transcript,
        voice_mode=cast(_VoiceModeLit, voice_mode),
        training_scenario=training_scenario,
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
