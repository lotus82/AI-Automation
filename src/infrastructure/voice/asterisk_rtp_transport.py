"""Транспорт Pipecat ↔ Asterisk: UDP RTP (PCMU), без тяжёлых кодеков в Python.

Важно: ARI «externalMedia» в Asterisk шлёт медиа на хост:порт по **UDP RTP**, а не на URI ws://.
Эндпоинт `/voice/stream` остаётся для браузера (Protobuf); SIP-медиа идёт сюда.
"""

from __future__ import annotations

import asyncio
import random
import struct
from dataclasses import dataclass, field

from loguru import logger
from pipecat.frames.frames import (
    CancelFrame,
    EndFrame,
    InputAudioRawFrame,
    OutputAudioRawFrame,
    StartFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.transports.base_input import BaseInputTransport
from pipecat.transports.base_output import BaseOutputTransport
from pipecat.transports.base_transport import BaseTransport, TransportParams

from src.infrastructure.voice.g711 import (
    downsample_pcm16_24k_to_8k,
    pcm16_mono_to_ulaw,
    pcm8k_to_pcm16k_dup,
    ulaw_bytes_to_pcm16_mono,
)
from src.use_cases.interfaces import IVoiceTransport


def _rtp_ulaw_payload(data: bytes) -> bytes | None:
    """Снимает заголовок RTP (v2), возвращает полезную нагрузку PCMU."""
    if len(data) < 12:
        return None
    if (data[0] >> 6) != 2:
        return None
    csrc = data[0] & 0x0F
    pos = 12 + csrc * 4
    if len(data) < pos:
        return None
    if (data[0] >> 4) & 0x01:
        if len(data) < pos + 4:
            return None
        ext_len = int.from_bytes(data[pos + 2 : pos + 4], "big") * 4
        pos += 4 + ext_len
        if len(data) < pos:
            return None
    return data[pos:]


def _build_rtp_ulaw_packet(*, seq: int, ts: int, ssrc: int, payload: bytes) -> bytes:
    """RTP v2, PT=0 (PCMU), один маркер не выставляем (достаточно для Asterisk)."""
    b0 = 0x80
    b1 = 0x00  # PT 0
    return struct.pack("!BBHII", b0, b1, seq & 0xFFFF, ts & 0xFFFFFFFF, ssrc & 0xFFFFFFFF) + payload


@dataclass
class RtpMediaState:
    """Общее состояние сокета и счётчиков RTP для пары input/output."""

    port: int
    remote_addr: tuple[str, int] | None = None
    datagram_transport: asyncio.DatagramTransport | None = None
    seq: int = field(default_factory=lambda: random.randint(0, 32000))
    ts: int = 0
    ssrc: int = field(default_factory=lambda: random.randint(1, 2**31 - 1))
    closing: bool = False


class _RtpDatagramProtocol(asyncio.DatagramProtocol):
    def __init__(
        self,
        queue: asyncio.Queue[bytes],
        loop: asyncio.AbstractEventLoop,
        state: RtpMediaState,
    ) -> None:
        self._queue = queue
        self._loop = loop
        self._state = state

    def datagram_received(self, data: bytes, addr: tuple[str | int, int]) -> None:
        if self._state.remote_addr is None:
            self._state.remote_addr = (str(addr[0]), int(addr[1]))
            logger.info("RTP: первый пакет от %s:%s", self._state.remote_addr[0], self._state.remote_addr[1])
        self._loop.call_soon_threadsafe(self._queue.put_nowait, data)

    def error_received(self, exc: Exception) -> None:
        logger.warning("RTP UDP error_received: %s", exc)

    def connection_lost(self, exc: Exception | None) -> None:
        logger.debug("RTP UDP connection_lost: %s", exc)


class RtpUdpInputTransport(BaseInputTransport):
    """Вход: RTP PCMU → PCM16 @ 16 kHz для Deepgram."""

    def __init__(
        self,
        params: TransportParams,
        state: RtpMediaState,
        queue: asyncio.Queue[bytes],
        **kwargs: object,
    ) -> None:
        super().__init__(params, **kwargs)
        self._state = state
        self._queue = queue
        self._pump_task: asyncio.Task[None] | None = None
        self._initialized = False

    async def open_udp_socket(self) -> None:
        """Слушать UDP до вызова ARI externalMedia."""
        if self._state.datagram_transport is not None:
            return
        loop = asyncio.get_running_loop()
        transport, _ = await loop.create_datagram_endpoint(
            lambda: _RtpDatagramProtocol(self._queue, loop, self._state),
            local_addr=("0.0.0.0", self._state.port),
        )
        self._state.datagram_transport = transport
        logger.info("RTP: слушаем UDP 0.0.0.0:%s", self._state.port)

    async def start(self, frame: StartFrame) -> None:
        await super().start(frame)
        if self._initialized:
            return
        self._initialized = True
        if self._state.datagram_transport is None:
            raise RuntimeError("RTP: вызовите open_udp_socket() до запуска пайплайна")
        self._state.closing = False
        self._pump_task = self.create_task(self._pump_rtp())
        await self.set_transport_ready(frame)

    async def stop(self, frame: EndFrame) -> None:
        self._state.closing = True
        if self._pump_task:
            await self.cancel_task(self._pump_task)
            self._pump_task = None
        await super().stop(frame)
        if self._state.datagram_transport:
            self._state.datagram_transport.close()
            self._state.datagram_transport = None

    async def cancel(self, frame: CancelFrame) -> None:
        self._state.closing = True
        await super().cancel(frame)
        if self._pump_task:
            await self.cancel_task(self._pump_task)
            self._pump_task = None
        if self._state.datagram_transport:
            self._state.datagram_transport.close()
            self._state.datagram_transport = None

    async def _pump_rtp(self) -> None:
        while not self._state.closing:
            try:
                packet = await asyncio.wait_for(self._queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            payload = _rtp_ulaw_payload(packet)
            if not payload:
                continue
            pcm8k = ulaw_bytes_to_pcm16_mono(payload)
            pcm16k = pcm8k_to_pcm16k_dup(pcm8k)
            await self.push_audio_frame(
                InputAudioRawFrame(audio=pcm16k, sample_rate=16000, num_channels=1)
            )


class RtpUdpOutputTransport(BaseOutputTransport):
    """Выход: PCM от TTS → downsample → RTP PCMU обратно в Asterisk."""

    def __init__(
        self,
        params: TransportParams,
        state: RtpMediaState,
        **kwargs: object,
    ) -> None:
        super().__init__(params, **kwargs)
        self._state = state
        self._initialized = False

    async def start(self, frame: StartFrame) -> None:
        await super().start(frame)
        if self._initialized:
            return
        self._initialized = True
        await self.set_transport_ready(frame)

    async def write_audio_frame(self, frame: OutputAudioRawFrame) -> bool:
        dt = self._state.datagram_transport
        dest = self._state.remote_addr
        if dt is None or dest is None:
            return False
        pcm8k = downsample_pcm16_24k_to_8k(frame.audio)
        ulaw = pcm16_mono_to_ulaw(pcm8k)
        # 20 ms @ 8 kHz PCMU = 160 байт на пакет
        mtu_payload = 160
        for off in range(0, len(ulaw), mtu_payload):
            chunk = ulaw[off : off + mtu_payload]
            self._state.seq = (self._state.seq + 1) & 0xFFFF
            self._state.ts = (self._state.ts + len(chunk)) & 0xFFFFFFFF
            pkt = _build_rtp_ulaw_packet(
                seq=self._state.seq,
                ts=self._state.ts,
                ssrc=self._state.ssrc,
                payload=chunk,
            )
            try:
                dt.sendto(pkt, dest)
            except OSError as e:
                logger.warning("RTP sendto: %s", e)
                return False
        return True


class AsteriskRtpPipecatTransport(BaseTransport):
    """Pipecat BaseTransport: UDP RTP вместо WebSocket."""

    def __init__(self, rtp_port: int, *, input_name: str | None = None, output_name: str | None = None) -> None:
        super().__init__(input_name=input_name, output_name=output_name)
        self._state = RtpMediaState(port=rtp_port)
        self._queue: asyncio.Queue[bytes] = asyncio.Queue()
        params = TransportParams(
            audio_in_enabled=True,
            audio_in_sample_rate=16000,
            audio_in_channels=1,
            audio_out_enabled=True,
            audio_out_sample_rate=24000,
            audio_out_channels=1,
        )
        self._input = RtpUdpInputTransport(params, self._state, self._queue, name=self._input_name)
        self._output = RtpUdpOutputTransport(params, self._state, name=self._output_name)
        self._register_event_handler("on_client_disconnected")

    async def open_udp_socket(self) -> None:
        """Открыть сокет до ARI externalMedia."""
        await self._input.open_udp_socket()

    async def signal_disconnect(self) -> None:
        """Сигнал завершения сессии (например, ChannelDestroyed в ARI)."""
        await self._call_event_handler("on_client_disconnected", self, None)

    def input(self) -> FrameProcessor:
        return self._input

    def output(self) -> FrameProcessor:
        return self._output


class PipecatAsteriskRtpVoiceTransport(IVoiceTransport):
    """Обёртка под тот же порт IVoiceTransport, что и WebSocket-транспорт."""

    def __init__(self, inner: AsteriskRtpPipecatTransport) -> None:
        self._inner = inner

    @property
    def pipecat_transport(self) -> AsteriskRtpPipecatTransport:
        return self._inner

    def input_processor(self) -> FrameProcessor:
        return self._inner.input()

    def output_processor(self) -> FrameProcessor:
        return self._inner.output()
