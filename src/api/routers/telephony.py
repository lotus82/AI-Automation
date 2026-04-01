"""Вебхуки для АТС: входящие вызовы и события (SIP)."""

from __future__ import annotations

from fastapi import APIRouter, Request, status

from src.api.schemas.telephony import (
    TelephonyEventRequest,
    TelephonyInboundRequest,
    TelephonyInboundResponse,
)
from src.core.config import get_settings
from src.infrastructure.sip_call_redis import (
    analyst_call_meta_redis_key,
    decode_sip_call_map_session_id,
    encode_analyst_call_meta,
    encode_sip_call_map,
    sip_call_map_redis_key,
)
from src.infrastructure.voice.sip_pipecat_adapter import build_telephony_service
from src.workers.tasks import analyze_conversation_task

router = APIRouter(tags=["telephony"])

# TODO: Проверка подписи или секрета от PBX (заголовок X-Telephony-Token / TELEPHONY_WEBHOOK_SECRET).


@router.post(
    "/telephony/inbound",
    response_model=TelephonyInboundResponse,
    status_code=status.HTTP_200_OK,
    summary="Входящий вызов (SIP)",
)
async def telephony_inbound(
    body: TelephonyInboundRequest,
    request: Request,
) -> TelephonyInboundResponse:
    """АТС сообщает о новом входящем канале; возвращаем session_id для Redis и моста с Pipecat."""
    settings = get_settings()
    redis = request.app.state.redis
    telephony = build_telephony_service(settings)
    session_id = await telephony.handle_inbound_call(body.call_id.strip())
    ttl = settings.chat_memory_ttl_seconds
    await redis.setex(
        analyst_call_meta_redis_key(session_id),
        ttl,
        encode_analyst_call_meta(
            direction="inbound",
            remote_phone=body.caller_phone.strip(),
        ),
    )
    await redis.setex(
        sip_call_map_redis_key(body.call_id.strip()),
        ttl,
        encode_sip_call_map(session_id=session_id),
    )
    return TelephonyInboundResponse(session_id=session_id)


@router.post(
    "/telephony/event",
    status_code=status.HTTP_200_OK,
    summary="Событие вызова (ringing / answered / hung_up)",
)
async def telephony_event(
    body: TelephonyEventRequest,
    request: Request,
) -> dict[str, bool]:
    """Отслеживание статуса; при завершении вызова — постановка задачи ОКК/аналитика."""
    redis = request.app.state.redis
    cid = body.call_id.strip()
    map_key = sip_call_map_redis_key(cid)

    if body.status == "answered":
        # TODO: Запустить Pipecat с персоной консультанта, привязав аудио к session_id из Redis.
        return {"ok": True}

    if body.status == "hung_up":
        raw = await redis.get(map_key)
        session_id = decode_sip_call_map_session_id(raw)
        await redis.delete(map_key)
        if session_id:
            analyze_conversation_task.delay(session_id)
        return {"ok": True}

    # ringing — только телеметрия
    return {"ok": True}
