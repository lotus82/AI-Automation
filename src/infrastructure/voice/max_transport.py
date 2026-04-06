"""Мост PCM ↔ Pipecat для входящих VoIP-звонков MAX (инфраструктурный слой).

Вход: очередь фрагментов PCM16 mono 16 kHz (заполняется шлюзом к API звонков MAX).
Выход: TTS (24 kHz) → понижение до 16 kHz → асинхронный колбэк (отправка в медиасессию MAX).

# TODO (рус.): Реализовать приём RTP/WebRTC/WS от MAX и вызовы ``push_incoming_pcm16`` / колбэка исходящего потока по контракту Bot API.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from loguru import logger
from pipecat.frames.frames import (
    CancelFrame,
    EndFrame,
    InputAudioRawFrame,
    OutputAudioRawFrame,
    StartFrame,
)
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.transports.base_input import BaseInputTransport
from pipecat.transports.base_output import BaseOutputTransport
from pipecat.transports.base_transport import BaseTransport, TransportParams

from src.infrastructure.voice.g711 import downsample_pcm16_24k_to_16k
from src.use_cases.interfaces import IVoiceTransport

# 20 мс @ 16 kHz mono int16 = 640 байт (как типичный шаг для STT)
_PCM16_FRAME_BYTES = 640


OutgoingPCMHandler = Callable[[bytes], Awaitable[None]]


class MaxVoIPPCMInputTransport(BaseInputTransport):
    """Очередь PCM16 16 kHz → кадры ``InputAudioRawFrame`` для Deepgram/SaluteSpeech STT."""

    def __init__(
        self,
        params: TransportParams,
        queue: asyncio.Queue[bytes],
        **kwargs: object,
    ) -> None:
        super().__init__(params, **kwargs)
        self._queue = queue
        self._pump_task: asyncio.Task[None] | None = None
        self._buffer = bytearray()
        self._initialized = False
        self._closing = False

    async def start(self, frame: StartFrame) -> None:
        await super().start(frame)
        if self._initialized:
            return
        self._initialized = True
        self._closing = False
        self._pump_task = self.create_task(self._pump())
        await self.set_transport_ready(frame)

    async def stop(self, frame: EndFrame) -> None:
        self._closing = True
        if self._pump_task:
            await self.cancel_task(self._pump_task)
            self._pump_task = None
        await super().stop(frame)

    async def cancel(self, frame: CancelFrame) -> None:
        self._closing = True
        if self._pump_task:
            await self.cancel_task(self._pump_task)
            self._pump_task = None
        await super().cancel(frame)

    async def _pump(self) -> None:
        while not self._closing:
            try:
                chunk = await asyncio.wait_for(self._queue.get(), timeout=0.25)
                if chunk:
                    self._buffer.extend(chunk)
            except asyncio.TimeoutError:
                pass
            while len(self._buffer) >= _PCM16_FRAME_BYTES:
                raw = bytes(self._buffer[:_PCM16_FRAME_BYTES])
                del self._buffer[:_PCM16_FRAME_BYTES]
                await self.push_audio_frame(
                    InputAudioRawFrame(audio=raw, sample_rate=16000, num_channels=1)
                )


class MaxVoIPPCMOutputTransport(BaseOutputTransport):
    """Выход TTS: PCM 24 kHz → 16 kHz → колбэк (шлюз к MAX)."""

    def __init__(
        self,
        params: TransportParams,
        on_pcm16_mono: OutgoingPCMHandler | None,
        **kwargs: object,
    ) -> None:
        super().__init__(params, **kwargs)
        self._on_pcm16_mono = on_pcm16_mono
        self._initialized = False

    async def start(self, frame: StartFrame) -> None:
        await super().start(frame)
        if self._initialized:
            return
        self._initialized = True
        await self.set_transport_ready(frame)

    async def write_audio_frame(self, frame: OutputAudioRawFrame) -> bool:
        if not self._on_pcm16_mono:
            return True
        pcm16 = downsample_pcm16_24k_to_16k(frame.audio)
        if not pcm16:
            return True
        try:
            await self._on_pcm16_mono(pcm16)
        except Exception:
            logger.exception("MAX VoIP: сбой колбэка исходящего PCM")
            return False
        return True


class MaxVoIPPipecatTransport(BaseTransport):
    """Составной Pipecat-транспорт: вход из очереди, выход в колбэк."""

    def __init__(
        self,
        *,
        on_outgoing_pcm16_mono: OutgoingPCMHandler | None = None,
        input_name: str | None = None,
        output_name: str | None = None,
    ) -> None:
        super().__init__(input_name=input_name, output_name=output_name)
        self._queue: asyncio.Queue[bytes] = asyncio.Queue()
        params = TransportParams(
            audio_in_enabled=True,
            audio_in_sample_rate=16000,
            audio_in_channels=1,
            audio_out_enabled=True,
            audio_out_sample_rate=24000,
            audio_out_channels=1,
        )
        self._input = MaxVoIPPCMInputTransport(params, self._queue, name=self._input_name)
        self._output = MaxVoIPPCMOutputTransport(
            params,
            on_outgoing_pcm16_mono,
            name=self._output_name,
        )
        self._register_event_handler("on_client_disconnected")

    def push_incoming_pcm16(self, data: bytes) -> None:
        """Добавить сырой PCM16 LE mono 16 kHz (например из декодера RTP/WebRTC)."""
        if data:
            self._queue.put_nowait(data)

    async def signal_disconnect(self) -> None:
        """Завершить сессию (звонок сброшен со стороны MAX или таймаут)."""
        await self._call_event_handler("on_client_disconnected", self, None)

    def input(self) -> FrameProcessor:
        return self._input

    def output(self) -> FrameProcessor:
        return self._output


class MaxVoIPTransport(IVoiceTransport):
    """Обёртка ``IVoiceTransport`` для голосового оркестратора (аналог WebSocket-транспорта)."""

    def __init__(self, inner: MaxVoIPPipecatTransport) -> None:
        self._inner = inner

    @property
    def pipecat_transport(self) -> MaxVoIPPipecatTransport:
        return self._inner

    def input_processor(self) -> FrameProcessor:
        return self._inner.input()

    def output_processor(self) -> FrameProcessor:
        return self._inner.output()
