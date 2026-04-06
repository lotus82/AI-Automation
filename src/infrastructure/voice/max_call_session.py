"""Фоновая обработка входящего VoIP-звонка MAX: задержка → accept → Pipecat (RAG/CRM как у телефонии)."""

from __future__ import annotations

import asyncio
import logging

from redis.asyncio import Redis

from src.core.config import Settings
from src.domain import system_setting_keys as sk
from src.infrastructure.database import AsyncSessionLocal
from src.infrastructure.repositories import PostgresSettingsRepository
from src.infrastructure.services.max_messenger import MaxMessengerClient
from src.infrastructure.voice.max_transport import MaxVoIPPipecatTransport, MaxVoIPTransport
from src.infrastructure.voice.voice_session import (
    run_voice_pipeline_session,
    schedule_analyze_after_voice,
)

logger = logging.getLogger(__name__)

_DEFAULT_GREETING = "Здравствуйте! Это ИИ-помощник компании. Слушаю вас."


async def _noop_outgoing_pcm(_data: bytes) -> None:
    """Заглушка до подключения медиашлюза MAX (# TODO (рус.): отправлять PCM в сокет/WebRTC по контракту API)."""
    return


async def run_max_inbound_call_background(
    *,
    call_id: str,
    user_label: str | None,
    redis: Redis,
    settings: Settings,
) -> None:
    """Полный цикл: чтение задержки/приветствия из БД → sleep → answer_call → голосовой пайплайн."""
    log_prefix = f"MAX VoIP call_id={call_id}"
    try:
        async with AsyncSessionLocal() as session:
            try:
                repo = PostgresSettingsRepository(session, redis)
                delay_raw = (await repo.get_value(sk.MAX_CALL_ANSWER_DELAY) or "6").strip()
                greeting = (await repo.get_value(sk.MAX_CALL_GREETING_PHRASE) or "").strip()
                if not greeting:
                    greeting = _DEFAULT_GREETING
                await session.commit()
            except Exception:
                await session.rollback()
                raise

        try:
            delay_sec = max(0, min(120, int(delay_raw)))
        except ValueError:
            delay_sec = 6

        logger.info("%s: ожидание перед ответом %s с", log_prefix, delay_sec)
        await asyncio.sleep(delay_sec)

        async with AsyncSessionLocal() as session:
            try:
                repo = PostgresSettingsRepository(session, redis)
                mx = MaxMessengerClient(
                    settings_repository=repo,
                    api_base_url=settings.max_api_base,
                    platform_api_base_url=settings.max_platform_api_base,
                    env_fallback_max_bot_token=settings.max_bot_token,
                )
                await mx.answer_call(call_id)
                await session.commit()
            except Exception:
                await session.rollback()
                raise

        bridge = MaxVoIPPipecatTransport(on_outgoing_pcm16_mono=_noop_outgoing_pcm)
        transport = MaxVoIPTransport(bridge)
        session_id = f"max_call_{call_id}"

        await run_voice_pipeline_session(
            session_id=session_id,
            voice_transport=transport,
            redis=redis,
            settings=settings,
            voice_mode="consultant",
            training_scenario=None,
            fixed_greeting_phrase=greeting,
            voice_user_name=user_label,
        )
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("%s: сбой обработки", log_prefix)
    finally:
        schedule_analyze_after_voice(f"max_call_{call_id}")
