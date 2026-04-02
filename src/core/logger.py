"""Обработчик логов для трансляции в WebSocket (панель отладки MAX)."""

from __future__ import annotations

import logging
from typing import Final

from src.infrastructure.monitoring.log_ws_broadcaster import schedule_log_broadcast

# Имена логгеров, чьи записи уходят в ``/api/ws/logs`` (stdlib logging).
_WS_TARGET_LOGGERS: Final[tuple[str, ...]] = (
    "src.use_cases.chat",
    "src.api.routers.max_bot",
    "src.infrastructure.services.dynamic_llm",
    "src.infrastructure.services.max_messenger",
)

_ws_handler_attached = False


class WebSocketLogHandler(logging.Handler):
    """Отправляет отформатированные сообщения в ``LogWebSocketBroadcaster`` (включая traceback при ``exc_info``)."""

    def __init__(self, level: int = logging.DEBUG) -> None:
        super().__init__(level=level)
        self.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

    def emit(self, record: logging.LogRecord) -> None:
        try:
            text = self.format(record)
            schedule_log_broadcast(
                level=record.levelname,
                logger_name=record.name,
                message=text,
            )
        except Exception:
            self.handleError(record)


def attach_ws_log_handlers(*, debug: bool = False) -> None:
    """Подключает ``WebSocketLogHandler`` к целевым логгерам (идемпотентно)."""
    global _ws_handler_attached
    if _ws_handler_attached:
        return
    handler = WebSocketLogHandler(level=logging.DEBUG if debug else logging.INFO)
    for name in _WS_TARGET_LOGGERS:
        log = logging.getLogger(name)
        log.addHandler(handler)
        log.setLevel(logging.DEBUG if debug else logging.INFO)
        log.propagate = True
    _ws_handler_attached = True
