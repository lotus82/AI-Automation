"""In-memory широковещание событий чата всем подключённым WebSocket-клиентам панели."""

from __future__ import annotations

import asyncio
import json
from uuid import UUID

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


def _listener_wants_event(listener_scope: UUID | None, event_org: UUID | None) -> bool:
    """Подписчик с областью ``UUID`` видит только события этой организации; ``None`` — только legacy (без org)."""
    if listener_scope is not None:
        return event_org == listener_scope
    return event_org is None


class ChatEventsBroadcaster(IChatMonitoringPublisher):
    """Наблюдатель: при новой реплике рассылает JSON подписчикам ``/api/ws/monitoring`` с учётом организации."""

    def __init__(self) -> None:
        self._connections: dict[WebSocket, UUID | None] = {}
        self._lock = asyncio.Lock()

    async def adopt(self, websocket: WebSocket, *, listener_scope: UUID | None) -> None:
        """Добавить уже принятый (``accept``) сокет; ``listener_scope`` — изоляция как у REST ``/chats``."""
        async with self._lock:
            self._connections[websocket] = listener_scope

    async def register(self, websocket: WebSocket, *, listener_scope: UUID | None) -> None:
        await websocket.accept()
        await self.adopt(websocket, listener_scope=listener_scope)

    async def unregister(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.pop(websocket, None)

    async def publish_new_message(
        self,
        *,
        session_id: str,
        role: str,
        content: str,
        user_info: str | None = None,
        organization_id: UUID | None = None,
    ) -> None:
        safe_content = content if len(content) <= _WS_CONTENT_MAX else content[: _WS_CONTENT_MAX] + "…"
        event = {
            "type": "new_message",
            "session_id": session_id,
            "role": role,
            "content": safe_content,
            "user_info": user_info or "",
            "organization_id": str(organization_id) if organization_id else None,
        }
        raw = json.dumps(event, ensure_ascii=False)
        async with self._lock:
            targets = list(self._connections.items())
        dead: list[WebSocket] = []
        for ws, listener_scope in targets:
            if not _listener_wants_event(listener_scope, organization_id):
                continue
            try:
                await ws.send_text(raw)
            except Exception:
                dead.append(ws)
                logger.debug("Отключён клиент мониторинга (send_text)")
        if dead:
            async with self._lock:
                for ws in dead:
                    self._connections.pop(ws, None)
