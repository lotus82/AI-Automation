"""Реализация IVoiceTransport поверх Pipecat FastAPI WebSocket."""

from __future__ import annotations

from typing import Any

from pipecat.frames.frames import Frame, TranscriptionFrame
from pipecat.transports.network.fastapi_websocket import (
    FastAPIWebsocketOutputTransport,
    FastAPIWebsocketTransport,
)

from src.use_cases.interfaces import IVoiceTransport


class TranscriptForwardingFastAPIWebsocketOutputTransport(FastAPIWebsocketOutputTransport):
    """Pipecat 0.0.x: в WebSocket через sink уходит только PCM; TranscriptionFrame иначе не сериализуется."""

    async def _sink_frame_handler(self, frame: Frame) -> None:
        if isinstance(frame, TranscriptionFrame):
            await self._write_frame(frame)
        await super()._sink_frame_handler(frame)


def replace_fastapi_output_with_transcript_forwarding(
    transport: FastAPIWebsocketTransport,
) -> None:
    """Подмена выходного транспорта после ``FastAPIWebsocketTransport(...)`` (без копирования его ``__init__``)."""
    old = transport._output
    name = getattr(old, "name", None)
    kwargs: dict[str, Any] = {}
    if name is not None:
        kwargs["name"] = name
    transport._output = TranscriptForwardingFastAPIWebsocketOutputTransport(
        transport,
        transport._client,
        transport._params,
        **kwargs,
    )


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
