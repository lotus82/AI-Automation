"""Базовая настройка логирования для приложения."""

import logging
import sys
from typing import Any

from src.core.logger import attach_ws_log_handlers


def setup_logging(*, debug: bool = False) -> None:
    """Настраивает корневой логгер: уровень, stderr и трансляцию в WebSocket (панель «Боты»)."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stderr,
        force=True,
    )
    attach_ws_log_handlers(debug=debug)


def get_logger(name: str) -> logging.Logger:
    """Возвращает именованный логгер (обёртка для единообразия)."""
    return logging.getLogger(name)
