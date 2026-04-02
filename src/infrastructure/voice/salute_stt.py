"""Потоковое распознавание SaluteSpeech по gRPC (Pipecat 0.0.60, STTService).

Контракт: ``smartspeech.recognition.v2`` — RPC **Recognize** (bidirectional stream).
Ответы приходят в ``RecognitionResponse`` с ``oneof response``; текст — в ветке **transcription**.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, AsyncIterator
from typing import Any

import grpc
import grpc.aio
from google.protobuf import duration_pb2
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

from src.infrastructure.services.salute_auth import SaluteSpeechAuthManager
from src.infrastructure.voice.salute_grpc_tls import smartspeech_channel_credentials
from src.infrastructure.voice.sber_protos import recognition_pb2, recognition_pb2_grpc

# Лимит Сбера: до ~4 Мб на сообщение; ~2 с аудио на чанк при 16 kHz mono S16LE ≈ 64000 байт.
_MAX_BYTES_PER_CHUNK = 64000


def _language_from_tag(tag: str) -> Language:
    t = (tag or "ru-RU").strip()
    try:
        return Language(t)
    except ValueError:
        try:
            return Language(t.split("-", 1)[0])
        except ValueError:
            return Language.RU_RU


def _best_hypothesis_text(results: list) -> str:
    """Берём нормализованный текст гипотезы или сырой ``text``."""
    parts: list[str] = []
    for h in results:
        nt = (getattr(h, "normalized_text", None) or "").strip()
        raw = (getattr(h, "text", None) or "").strip()
        seg = nt or raw
        if seg:
            parts.append(seg)
    return " ".join(parts).strip()


class SaluteSpeechSTTService(STTService):
    """STT: ``SmartSpeech/Recognize`` (stream) на ``grpc.aio``, Bearer-токен в metadata."""

    def __init__(
        self,
        *,
        auth_manager: SaluteSpeechAuthManager,
        grpc_target: str = "smartspeech.sber.ru:443",
        language: str = "ru-RU",
        model: str = "general",
        smartspeech_verify_ssl: bool = True,
        sample_rate: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(sample_rate=sample_rate, **kwargs)
        self._register_event_handler("on_speech_started")
        self._auth = auth_manager
        self._grpc_target = grpc_target.strip()
        self._language = language
        self._model = (model or "general").strip()
        self._verify_ssl = smartspeech_verify_ssl

        self._closing = False
        self._pcm_buffer = bytearray()
        self._send_queue: asyncio.Queue[bytes | None] | None = None
        self._recognition_task: asyncio.Task[None] | None = None
        self._utterance_speech_event_fired = False
        self._active_grpc_channel: grpc.aio.Channel | None = None

    def can_generate_metrics(self) -> bool:
        return True

    def _grpc_metadata(self, token: str) -> tuple[tuple[str, str], ...]:
        return (("authorization", f"Bearer {token}"),)

    async def _get_channel_credentials(self) -> grpc.ChannelCredentials:
        if self._verify_ssl:
            return smartspeech_channel_credentials(self._grpc_target, True)
        return await asyncio.to_thread(
            smartspeech_channel_credentials, self._grpc_target, False
        )

    def _build_recognition_options(self) -> recognition_pb2.RecognitionOptions:
        # v2: флаги через OptionalBool; порядок полей см. recognition.proto
        opts = recognition_pb2.RecognitionOptions(
            audio_encoding=recognition_pb2.RecognitionOptions.PCM_S16LE,
            sample_rate=int(self.sample_rate or 16000),
            channels_count=1,
            language=self._language,
            model=self._model,
            hypotheses_count=1,
        )
        opts.enable_multi_utterance.CopyFrom(recognition_pb2.OptionalBool(enable=True))
        opts.enable_partial_results.CopyFrom(recognition_pb2.OptionalBool(enable=True))
        opts.no_speech_timeout.CopyFrom(duration_pb2.Duration(seconds=7))
        opts.max_speech_timeout.CopyFrom(duration_pb2.Duration(seconds=20))
        # Мат-фильтр и прочая нормализация — в NormalizationOptions (v1 enable_profanity_filter снят)
        opts.normalization_options.profanity_filter.CopyFrom(
            recognition_pb2.OptionalBool(enable=False)
        )
        return opts

    async def start(self, frame: StartFrame) -> None:
        await super().start(frame)
        await self._auth.prewarm()
        self._closing = False
        self._pcm_buffer = bytearray()
        self._send_queue = asyncio.Queue()
        self._utterance_speech_event_fired = False
        self._recognition_task = self.create_task(self._recognition_worker())

    async def stop(self, frame: EndFrame) -> None:
        await self._shutdown_grpc()
        await super().stop(frame)

    async def cancel(self, frame: CancelFrame) -> None:
        await self._shutdown_grpc()
        await super().cancel(frame)

    async def _shutdown_grpc(self) -> None:
        self._closing = True
        ch = self._active_grpc_channel
        if ch is not None:
            self._active_grpc_channel = None
            try:
                await ch.close()
            except Exception:
                pass
        if self._send_queue is not None:
            if self._pcm_buffer:
                await self._send_queue.put(bytes(self._pcm_buffer))
                self._pcm_buffer.clear()
            await self._send_queue.put(None)
        if self._recognition_task is not None:
            self._recognition_task.cancel()
            try:
                await self._recognition_task
            except asyncio.CancelledError:
                pass
            self._recognition_task = None
        self._send_queue = None

    async def run_stt(self, audio: bytes) -> AsyncGenerator[Frame, None]:
        """Контракт STTService; при gRPC не используется (аудио уходит в ``process_audio_frame``)."""
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

    async def _request_iterator(self) -> AsyncIterator[recognition_pb2.RecognitionRequest]:
        assert self._send_queue is not None
        yield recognition_pb2.RecognitionRequest(options=self._build_recognition_options())
        while True:
            chunk = await self._send_queue.get()
            if chunk is None:
                break
            # Дробим на подчанки, если в очередь попало большое значение.
            for off in range(0, len(chunk), _MAX_BYTES_PER_CHUNK):
                sub = chunk[off : off + _MAX_BYTES_PER_CHUNK]
                if sub:
                    yield recognition_pb2.RecognitionRequest(audio_chunk=sub)

    async def _handle_response(self, resp: recognition_pb2.RecognitionResponse) -> None:
        branch = resp.WhichOneof("response")
        if branch == "backend_info":
            bi = resp.backend_info
            logger.trace(
                "SaluteSpeech STT: backend_info model={} ver={}",
                bi.model_name,
                bi.model_version,
            )
            return
        if branch == "insight":
            logger.trace("SaluteSpeech STT: insight len={}", len(resp.insight.insight_result or ""))
            return
        if branch == "vad":
            return
        if branch != "transcription":
            return

        tr = resp.transcription
        if not tr.results:
            return
        text = _best_hypothesis_text(list(tr.results))
        if not text:
            return
        lang = _language_from_tag(self._language)

        if not tr.eou:
            if not self._utterance_speech_event_fired:
                self._utterance_speech_event_fired = True
                await self._call_event_handler("on_speech_started", self)
                await self.start_ttfb_metrics()
                await self.start_processing_metrics()
            await self.push_frame(
                InterimTranscriptionFrame(text, "", time_now_iso8601(), lang)
            )
            return

        await self.stop_ttfb_metrics()
        await self.push_frame(TranscriptionFrame(text, "", time_now_iso8601(), lang))
        await self.stop_processing_metrics()
        self._utterance_speech_event_fired = False

    async def _one_recognize_stream(self) -> None:
        token = await self._auth.get_access_token()
        creds = await self._get_channel_credentials()
        channel = grpc.aio.secure_channel(self._grpc_target, creds)
        self._active_grpc_channel = channel
        stub = recognition_pb2_grpc.SmartSpeechStub(channel)
        metadata = self._grpc_metadata(token)
        try:
            call = stub.Recognize(self._request_iterator(), metadata=metadata)
            async for resp in call:
                if self._closing:
                    break
                await self._handle_response(resp)
        except grpc.aio.AioRpcError as err:
            if err.code() == grpc.StatusCode.UNAUTHENTICATED:
                await self._auth.invalidate_cache()
            raise
        finally:
            if self._active_grpc_channel is channel:
                self._active_grpc_channel = None
                try:
                    await channel.close()
                except Exception:
                    pass

    async def _recognition_worker(self) -> None:
        """Цикл: сервер может закрывать stream после фразы — поднимаем заново, пока сессия жива."""
        retry_delay = 0.4
        while not self._closing:
            try:
                await self._one_recognize_stream()
            except asyncio.CancelledError:
                raise
            except grpc.aio.AioRpcError as err:
                if self._closing:
                    break
                logger.warning("SaluteSpeech STT gRPC: {} — {}", err.code(), err.details())
                await asyncio.sleep(retry_delay)
            except Exception as exc:
                if self._closing:
                    break
                logger.exception("SaluteSpeech STT gRPC: {}", exc)
                await self.push_error(ErrorFrame(f"SaluteSpeech STT: {exc}"))
                await asyncio.sleep(retry_delay)
            else:
                if self._closing:
                    break
                # Нормальное закрытие со стороны сервиса после EOU — сразу новый stream.
                await asyncio.sleep(0.02)
