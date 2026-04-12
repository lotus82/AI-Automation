"""In-memory широковещание событий чата всем подключённым WebSocket-клиентам панели."""

from __future__ import annotations

import asyncio
import json

from fastapi import WebSocket
from loguru import logger

from src.use_cases.interfaces import IChatMonitoringPublisher

# Максимальная длина текста в событии WS (защита от перегрузки панели).
_WS_CONTENT_MAX = 8000

_broadcaster_instance: ChatEventsBroadcaster | None = None


def get_chat_events_broadcaster() -> ChatEventsBroadcaster:
    """Общий экземпляр на процесс (FastAPI + фоновые вызовы use case)."""
    global _broadcaster_instance
    if _broadcaster_instance is None:
        _broadcaster_instance = ChatEventsBroadcaster()
    return _broadcaster_instance


class ChatEventsBroadcaster(IChatMonitoringPublisher):
    """Наблюдатель: при новой реплике рассылает JSON всем подписчикам ``/api/ws/monitoring``."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def adopt(self, websocket: WebSocket) -> None:
        """Добавить уже принятый (``accept``) сокет в пул рассылки."""
        async with self._lock:
            self._connections.add(websocket)

    async def register(self, websocket: WebSocket) -> None:
        await websocket.accept()
        await self.adopt(websocket)

    async def unregister(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(websocket)

    async def publish_new_message(
        self,
        *,
        session_id: str,
        role: str,
        content: str,
        user_info: str | None = None,
    ) -> None:
        safe_content = content if len(content) <= _WS_CONTENT_MAX else content[: _WS_CONTENT_MAX] + "…"
        event = {
            "type": "new_message",
            "session_id": session_id,
            "role": role,
            "content": safe_content,
            "user_info": user_info or "",
        }
        raw = json.dumps(event, ensure_ascii=False)
        async with self._lock:
            targets = list(self._connections)
        dead: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_text(raw)
            except Exception:
                dead.append(ws)
                logger.debug("Отключён клиент мониторинга (send_text)")
        if dead:
            async with self._lock:
                for ws in dead:
                    self._connections.discard(ws)
