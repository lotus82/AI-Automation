"""WebSocket-уведомления для панели мониторинга диалогов и поток логов отладки."""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.infrastructure.monitoring import get_chat_events_broadcaster
from src.infrastructure.monitoring.log_ws_broadcaster import get_log_ws_broadcaster

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


@router.websocket("/ws/logs")
async def logs_websocket(websocket: WebSocket) -> None:
    """Поток логов приложения для режима отладки MAX (см. ``WebSocketLogHandler`` / ``src/core/logger.py``)."""
    broadcaster = get_log_ws_broadcaster()
    await broadcaster.register(websocket)
    try:
        while True:
            # Удерживаем соединение; клиент может слать ping.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await broadcaster.unregister(websocket)
