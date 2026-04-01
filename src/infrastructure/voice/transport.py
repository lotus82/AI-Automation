"""Реализация IVoiceTransport поверх Pipecat FastAPI WebSocket."""

from __future__ import annotations

from typing import Any

from pipecat.transports.network.fastapi_websocket import FastAPIWebsocketTransport

from src.use_cases.interfaces import IVoiceTransport


class PipecatWebSocketVoiceTransport(IVoiceTransport):
    """Обёртка над Pipecat FastAPIWebsocketTransport (инфраструктурная деталь)."""

    def __init__(self, inner: FastAPIWebsocketTransport) -> None:
        self._inner = inner

    @property
    def pipecat_transport(self) -> FastAPIWebsocketTransport:
        """Доступ к нативному транспорту для event_handler (только инфраструктура)."""
        return self._inner

    def input_processor(self) -> Any:
        return self._inner.input()

    def output_processor(self) -> Any:
        return self._inner.output()
