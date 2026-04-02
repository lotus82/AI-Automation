"""Трансляция текстовых логов подписчикам WebSocket ``/api/ws/logs`` (режим отладки панели «Боты»)."""

from __future__ import annotations

import asyncio
import json

from fastapi import WebSocket

# Глобальный экземпляр на процесс (как у ChatEventsBroadcaster).
_broadcaster_instance: LogWebSocketBroadcaster | None = None


def get_log_ws_broadcaster() -> LogWebSocketBroadcaster:
    """Возвращает синглтон широковещателя логов."""
    global _broadcaster_instance
    if _broadcaster_instance is None:
        _broadcaster_instance = LogWebSocketBroadcaster()
    return _broadcaster_instance


class LogWebSocketBroadcaster:
    """Рассылает JSON-события ``{type, level, logger, message}`` всем клиентам ``/api/ws/logs``."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def register(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)

    async def unregister(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(websocket)

    async def publish(self, payload: dict) -> None:
        raw = json.dumps(payload, ensure_ascii=False)
        async with self._lock:
            targets = list(self._connections)
        dead: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_text(raw)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._connections.discard(ws)


def schedule_log_broadcast(*, level: str, logger_name: str, message: str) -> None:
    """Планирует отправку строки лога всем WS-клиентам (из синхронного ``logging.Handler.emit``)."""
    payload = {
        "type": "log",
        "level": level.upper(),
        "logger": logger_name,
        "message": message,
    }

    async def _send() -> None:
        await get_log_ws_broadcaster().publish(payload)

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    loop.create_task(_send())
