"""WebSocket-эндпоинт голосового потока (Pipecat + RAG / тренажёр)."""

from __future__ import annotations

from typing import Literal, cast
from uuid import UUID, uuid4

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from loguru import logger
from redis.asyncio import Redis

from src.core.config import get_settings
from src.domain.entities import TrainingScenario
from src.infrastructure.database import AsyncSessionLocal
from src.infrastructure.repositories import SqlAlchemyTrainingScenarioRepository
from src.infrastructure.training_session_redis import (
    encode_trainer_meta,
    trainer_session_redis_key,
)
from src.infrastructure.voice.voice_session import (
    run_voice_pipeline_session,
    schedule_analyze_after_voice,
)
router = APIRouter()

_VoiceModeLit = Literal["consultant", "trainer_client"]


def _parse_session_id(raw: str | None) -> str:
    if raw is None or raw == "":
        return str(uuid4())
    try:
        UUID(raw)
    except ValueError:
        return str(uuid4())
    return raw


def _parse_voice_mode(raw: str | None) -> str:
    """consultant — ИИ консультант; trainer / trainer_client — ИИ играет клиента."""
    v = (raw or "consultant").strip().lower()
    if v in ("trainer", "trainer_client"):
        return "trainer_client"
    return "consultant"


@router.websocket("/stream")
async def voice_stream(
    websocket: WebSocket,
    session_id: str | None = Query(default=None, description="UUID сессии для Redis-памяти"),
    mode: str | None = Query(
        default="consultant",
        description="consultant — ИИ-продавец; trainer — ИИ-клиент (нужен scenario_id)",
    ),
    scenario_id: str | None = Query(
        default=None,
        description="UUID сценария тренажёра (обязателен при mode=trainer)",
    ),
    manager_name: str | None = Query(
        default=None,
        description="Имя менеджера для отчёта тренера (опционально)",
    ),
) -> None:
    """Двунаправленный поток: PCM через Pipecat Protobuf; STT→RAG→TTS или режим тренажёра.

    Входящие SIP-звонки через Asterisk используют **UDP RTP** (см. ARI + AsteriskRtpPipecatTransport),
    а не этот WebSocket — см. README, фаза 11.
    """
    # Тяжёлые импорты Pipecat только при реальном подключении к голосу (не при старте API).
    from pipecat.serializers.protobuf import ProtobufFrameSerializer
    from pipecat.transports.network.fastapi_websocket import (
        FastAPIWebsocketParams,
        FastAPIWebsocketTransport,
    )
    from src.infrastructure.voice import PipecatWebSocketVoiceTransport

    settings = get_settings()
    await websocket.accept()

    if not settings.deepgram_api_key:
        await websocket.close(code=1008, reason="Не задан DEEPGRAM_API_KEY")
        return

    sid = _parse_session_id(session_id)
    redis: Redis = websocket.app.state.redis
    voice_mode = _parse_voice_mode(mode)
    training_scenario: TrainingScenario | None = None

    meta_key = trainer_session_redis_key(sid)
    if voice_mode == "trainer_client":
        if not scenario_id or not scenario_id.strip():
            await websocket.close(code=1008, reason="Для режима trainer нужен scenario_id")
            return
        try:
            sc_uuid = UUID(scenario_id.strip())
        except ValueError:
            await websocket.close(code=1008, reason="Некорректный scenario_id (ожидается UUID)")
            return
        async with AsyncSessionLocal() as session:
            try:
                repo = SqlAlchemyTrainingScenarioRepository(session)
                training_scenario = await repo.get_by_id(sc_uuid)
                await session.commit()
            except Exception:
                await session.rollback()
                raise
        if training_scenario is None:
            await websocket.close(code=1008, reason="Сценарий не найден")
            return
        await redis.setex(
            meta_key,
            settings.chat_memory_ttl_seconds,
            encode_trainer_meta(
                scenario_id=str(training_scenario.id),
                manager_name=manager_name or "",
            ),
        )
    else:
        await redis.delete(meta_key)

    params = FastAPIWebsocketParams(
        audio_in_enabled=True,
        audio_in_sample_rate=16000,
        audio_out_enabled=True,
        audio_out_sample_rate=24000,
        serializer=ProtobufFrameSerializer(),
    )
    pipecat_transport = FastAPIWebsocketTransport(websocket=websocket, params=params)
    voice_transport = PipecatWebSocketVoiceTransport(pipecat_transport)

    try:
        await run_voice_pipeline_session(
            session_id=sid,
            voice_transport=voice_transport,
            redis=redis,
            settings=settings,
            voice_mode=cast(_VoiceModeLit, voice_mode),
            training_scenario=training_scenario,
        )
    except WebSocketDisconnect:
        logger.info("WebSocket голоса отключён клиентом (session_id=%s)", sid)
    except Exception:
        logger.exception("Сбой голосового пайплайна (session_id=%s)", sid)
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
    finally:
        schedule_analyze_after_voice(sid)
