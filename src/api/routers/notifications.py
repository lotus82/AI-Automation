"""WebSocket-уведомления для панели мониторинга диалогов."""

from __future__ import annotations

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from src.core.config import get_settings
from src.infrastructure.monitoring import get_chat_events_broadcaster
from src.infrastructure.portal_security import decode_portal_token

router = APIRouter(tags=["notifications"])


@router.websocket("/ws/monitoring")
async def monitoring_websocket(
    websocket: WebSocket,
    token: str | None = Query(default=None, description="JWT портала (тот же, что в Authorization для REST)"),
) -> None:
    """Подписка на события ``new_message`` (рассылает ``ChatEventsBroadcaster``)."""
    await websocket.accept()
    if not token or not token.strip():
        await websocket.close(code=1008, reason="Unauthorized")
        return
    try:
        payload = decode_portal_token(token.strip(), get_settings().portal_jwt_secret)
        if payload.get("typ") != "portal" or not payload.get("sub"):
            raise ValueError("bad token")
    except Exception:
        await websocket.close(code=1008, reason="Unauthorized")
        return

    broadcaster = get_chat_events_broadcaster()
    await broadcaster.adopt(websocket)
    try:
        while True:
            # Держим соединение; клиент может слать ping-текст.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await broadcaster.unregister(websocket)
