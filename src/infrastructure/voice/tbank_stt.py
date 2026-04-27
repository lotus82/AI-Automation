"""Потоковый STT T-Bank VoiceKit (gRPC StreamingRecognize), Pipecat 0.0.60."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import grpc
import grpc.aio
from loguru import logger
from pipecat.frames.frames import (
    AudioRawFrame,
    CancelFrame,
    EndFrame,
    ErrorFrame,
    Frame,
    InterimTranscriptionFrame,
    StartFrame,
    TranscriptionFrame,
)
from pipecat.processors.frame_processor import FrameDirection
from pipecat.services.ai_services import STTService
from pipecat.transcriptions.language import Language
from pipecat.utils.time import time_now_iso8601

import src.infrastructure.voice.tbank_tinkoff_imports  # noqa: F401 — path для tinkoff.*
from tinkoff.cloud.stt.v1 import stt_pb2, stt_pb2_grpc

from src.infrastructure.voice.tbank_voicekit_auth import authorization_metadata
from src.infrastructure.voice.tbank_voicekit_config import TbankVoiceKitCredentials

_MAX_BYTES_PER_CHUNK = 64000
_SCOPE_STT = "tinkoff.cloud.stt"


def _to_pipecat_language(tag: str) -> Language:
    t = (tag or "ru-RU").strip()
    try:
        return Language(t)
    except ValueError:
        try:
            return Language(t.split("-", 1)[0])
        except ValueError:
            return Language.RU_RU


class TbankVoiceKitSTTService(STTService):
    """gRPC ``SpeechToText/StreamingRecognize``; PCM16 mono 16 kHz в сторону сервиса."""

    def __init__(
        self,
        *,
        credentials: TbankVoiceKitCredentials,
        language: str = "ru-RU",
        sample_rate: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(sample_rate=sample_rate, **kwargs)
        self._register_event_handler("on_speech_started")
        self._creds = credentials
        self._language = language
        self._closing = False
        self._pcm_buffer = bytearray()
        self._send_queue: asyncio.Queue[bytes | None] | None = None
        self._worker: asyncio.Task[None] | None = None
        self._fired_speech = False
        self._active_channel: grpc.aio.Channel | None = None

    def can_generate_metrics(self) -> bool:
        return True

    def _build_first_request(self) -> stt_pb2.StreamingRecognizeRequest:
        req = stt_pb2.StreamingRecognizeRequest()
        c = req.streaming_config.config
        c.encoding = stt_pb2.AudioEncoding.LINEAR16
        c.sample_rate_hertz = int(self.sample_rate or 16000)
        c.num_channels = 1
        c.language_code = self._language
        c.enable_automatic_punctuation = True
        req.streaming_config.single_utterance = False
        req.streaming_config.interim_results_config.enable_interim_results = True
        return req

    async def start(self, frame: StartFrame) -> None:
        await super().start(frame)
        self._closing = False
        self._pcm_buffer = bytearray()
        self._send_queue = asyncio.Queue()
        self._fired_speech = False
        self._worker = self.create_task(self._stream_worker())

    async def stop(self, frame: EndFrame) -> None:
        await self._shutdown()
        await super().stop(frame)

    async def cancel(self, frame: CancelFrame) -> None:
        await self._shutdown()
        await super().cancel(frame)

    async def _shutdown(self) -> None:
        self._closing = True
        if self._send_queue is not None:
            if self._pcm_buffer:
                await self._send_queue.put(bytes(self._pcm_buffer))
                self._pcm_buffer.clear()
            await self._send_queue.put(None)
        if self._worker is not None:
            self._worker.cancel()
            try:
                await self._worker
            except asyncio.CancelledError:
                pass
            self._worker = None
        self._send_queue = None
        ch = self._active_channel
        if ch is not None:
            self._active_channel = None
            try:
                await ch.close()
            except Exception:
                pass

    async def run_stt(self, audio: bytes) -> AsyncIterator[Frame]:  # noqa: ARG002
        del audio
        return
        yield  # pragma: no cover

    async def process_audio_frame(self, frame: AudioRawFrame, direction: FrameDirection) -> None:
        if self._muted or self._send_queue is None:
            return
        self._pcm_buffer.extend(frame.audio)
        while len(self._pcm_buffer) >= _MAX_BYTES_PER_CHUNK:
            chunk = bytes(self._pcm_buffer[:_MAX_BYTES_PER_CHUNK])
            del self._pcm_buffer[:_MAX_BYTES_PER_CHUNK]
            await self._send_queue.put(chunk)

    async def _request_iter(self) -> AsyncIterator[stt_pb2.StreamingRecognizeRequest]:
        assert self._send_queue is not None
        yield self._build_first_request()
        while True:
            chunk = await self._send_queue.get()
            if chunk is None:
                break
            for off in range(0, len(chunk), _MAX_BYTES_PER_CHUNK):
                sub = chunk[off : off + _MAX_BYTES_PER_CHUNK]
                if sub:
                    r = stt_pb2.StreamingRecognizeRequest()
                    r.audio_content = sub
                    yield r

    async def _stream_worker(self) -> None:
        metadata = authorization_metadata(
            self._creds.api_key, self._creds.secret_key, _SCOPE_STT, as_type=list
        )
        ch = grpc.aio.secure_channel(self._creds.grpc_target, grpc.ssl_channel_credentials())
        self._active_channel = ch
        stub = stt_pb2_grpc.SpeechToTextStub(ch)
        retry = 0.4
        while not self._closing:
            try:
                call = stub.StreamingRecognize(self._request_iter(), metadata=metadata)
                async for resp in call:
                    if self._closing:
                        break
                    await self._handle_response(resp)
            except asyncio.CancelledError:
                raise
            except grpc.aio.AioRpcError as err:
                if self._closing:
                    break
                logger.warning("T-Bank VoiceKit STT gRPC: {} — {}", err.code(), err.details())
                await self.push_error(ErrorFrame(f"T-Bank STT: {err.code()}"))
                await asyncio.sleep(retry)
            except Exception as exc:
                if self._closing:
                    break
                logger.exception("T-Bank VoiceKit STT gRPC: {}", exc)
                await self.push_error(ErrorFrame(f"T-Bank STT: {exc}"))
                await asyncio.sleep(retry)
            else:
                if self._closing:
                    break
                await asyncio.sleep(0.02)

    async def _handle_response(self, resp: stt_pb2.StreamingRecognizeResponse) -> None:
        lang = _to_pipecat_language(self._language)
        for r in resp.results:
            alts = list(r.recognition_result.alternatives)
            if not alts:
                continue
            text = (alts[0].transcript or "").strip()
            if not text:
                continue
            if r.is_final:
                if not self._fired_speech:
                    self._fired_speech = True
                    await self._call_event_handler("on_speech_started", self)
                    await self.start_ttfb_metrics()
                    await self.start_processing_metrics()
                await self.stop_ttfb_metrics()
                await self.push_frame(TranscriptionFrame(text, "", time_now_iso8601(), lang))
                await self.stop_processing_metrics()
                self._fired_speech = False
            else:
                if not self._fired_speech:
                    self._fired_speech = True
                    await self._call_event_handler("on_speech_started", self)
                    await self.start_ttfb_metrics()
                    await self.start_processing_metrics()
                await self.push_frame(InterimTranscriptionFrame(text, "", time_now_iso8601(), lang))
