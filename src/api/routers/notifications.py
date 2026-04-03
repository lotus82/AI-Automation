"""WebSocket-уведомления для панели мониторинга диалогов."""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.infrastructure.monitoring import get_chat_events_broadcaster

router = APIRouter(tags=["notifications"])


@router.websocket("/ws/monitoring")
async def monitoring_websocket(websocket: WebSocket) -> None:
    """Подписка на события ``new_message`` (рассылает ``ChatEventsBroadcaster``)."""
    broadcaster = get_chat_events_broadcaster()
    await broadcaster.register(websocket)
    try:
        while True:
            # Держим соединение; клиент может слать ping-текст.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await broadcaster.unregister(websocket)
