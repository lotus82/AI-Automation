"""Фоновый анализ завершённых диалогов: ОКК или оценка тренера (тренажёр)."""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from redis.asyncio import Redis

from src.core.config import get_settings
from src.domain.entities import CallAnalytics, CallRecord, TrainingSession
from src.infrastructure.database import AsyncSessionLocal
from src.infrastructure.repositories import (
    PostgresSettingsRepository,
    RedisChatMemoryRepository,
    SqlAlchemyCallRecordRepository,
    SqlAlchemyTrainingScenarioRepository,
    SqlAlchemyTrainingSessionRepository,
)
from src.infrastructure.services.dynamic_llm import DynamicLLMService
from src.infrastructure.sip_call_redis import (
    analyst_call_meta_redis_key,
    decode_analyst_call_meta,
)
from src.infrastructure.training_session_redis import (
    decode_trainer_meta,
    trainer_session_redis_key,
)

logger = logging.getLogger(__name__)


def _format_transcript(history: list[dict]) -> str:
    """Собирает плоский текст диалога для БД и LLM."""
    lines: list[str] = []
    for msg in history:
        role = msg.get("role", "?")
        content = msg.get("content", "")
        if isinstance(content, str) and content.strip():
            lines.append(f"{role}: {content.strip()}")
    return "\n".join(lines)


async def _analyze_async(session_id: str) -> str:
    settings = get_settings()
    redis = Redis.from_url(settings.redis_uri, decode_responses=True)
    try:
        memory = RedisChatMemoryRepository(
            redis,
            ttl_seconds=settings.chat_memory_ttl_seconds,
        )
        history = await memory.get_history(session_id)
        transcript = _format_transcript(history)
        if not transcript.strip():
            logger.info("История пуста, пропуск записи (session_id=%s)", session_id)
            return session_id

        ac_meta_raw = await redis.get(analyst_call_meta_redis_key(session_id))
        call_direction, remote_phone = decode_analyst_call_meta(ac_meta_raw)
        if ac_meta_raw:
            await redis.delete(analyst_call_meta_redis_key(session_id))

        meta_key = trainer_session_redis_key(session_id)
        meta_raw = await redis.get(meta_key)
        trainer_meta = decode_trainer_meta(meta_raw)

        sc_uuid: UUID | None = None
        manager_nm = ""
        if trainer_meta is not None:
            scenario_id_str, manager_nm = trainer_meta
            try:
                sc_uuid = UUID(scenario_id_str)
            except ValueError:
                logger.warning("Некорректный scenario_id в Redis: %s", scenario_id_str)
                sc_uuid = None

        if sc_uuid is not None and trainer_meta is not None:
            async with AsyncSessionLocal() as session:
                try:
                    scenario_repo = SqlAlchemyTrainingScenarioRepository(session)
                    call_repo = SqlAlchemyCallRecordRepository(session)
                    scenario = await scenario_repo.get_by_id(sc_uuid)
                    settings_repo = PostgresSettingsRepository(session, redis)
                    llm = DynamicLLMService(settings=settings, settings_repo=settings_repo)

                    record = CallRecord(
                        session_id=session_id,
                        duration=0,
                        status="training",
                        transcript_text=transcript,
                        direction=call_direction,
                        remote_phone=remote_phone,
                    )
                    saved = await call_repo.save(record)
                    if saved.id is None:
                        msg = "После сохранения call_record отсутствует id"
                        raise RuntimeError(msg)

                    if scenario is not None and scenario.id is not None:
                        score, feedback = await llm.analyze_training_performance(
                            transcript,
                            scenario_title=scenario.title,
                            objections_to_raise=scenario.objections_to_raise,
                        )
                        ts_repo = SqlAlchemyTrainingSessionRepository(session)
                        await ts_repo.save(
                            TrainingSession(
                                scenario_id=scenario.id,
                                manager_name=manager_nm or "—",
                                session_id=session_id,
                                score=score,
                                feedback_text=feedback,
                            )
                        )
                    else:
                        logger.warning(
                            "Сценарий %s не найден в БД, training_sessions не создан",
                            sc_uuid,
                        )

                    await session.commit()
                    logger.info(
                        "Тренер (LLM) завершён: session_id=%s, scenario_id=%s",
                        session_id,
                        sc_uuid,
                    )
                except Exception:
                    await session.rollback()
                    logger.exception("Сбой анализа тренировки (session_id=%s)", session_id)
                    raise
            await redis.delete(meta_key)
            return session_id

        # Обычный режим: ОКК качества ИИ-консультанта
        async with AsyncSessionLocal() as session:
            try:
                repo = SqlAlchemyCallRecordRepository(session)
                record = CallRecord(
                    session_id=session_id,
                    duration=0,
                    status="completed",
                    transcript_text=transcript,
                    direction=call_direction,
                    remote_phone=remote_phone,
                )
                saved = await repo.save(record)
                if saved.id is None:
                    msg = "После сохранения call_record отсутствует id"
                    raise RuntimeError(msg)

                settings_repo = PostgresSettingsRepository(session, redis)
                llm = DynamicLLMService(settings=settings, settings_repo=settings_repo)
                score, recommendations = await llm.analyze_conversation_quality(transcript)
                analytics = CallAnalytics(
                    call_record_id=saved.id,
                    score=score,
                    recommendations=recommendations,
                )
                await repo.save_analytics(analytics)
                await session.commit()
                logger.info(
                    "ОКК завершён: session_id=%s, call_id=%s, score=%s",
                    session_id,
                    saved.id,
                    score,
                )
            except Exception:
                await session.rollback()
                logger.exception("Сбой задачи анализа диалога (session_id=%s)", session_id)
                raise
        return session_id
    finally:
        await redis.aclose()


def analyze_conversation_sync(session_id: str) -> str:
    """Синхронная обёртка для вызова из Celery worker."""
    return asyncio.run(_analyze_async(session_id))
