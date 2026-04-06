"""Синтез SaluteSpeech по gRPC (``SmartSpeech/Synthesize``) для Pipecat 0.0.60."""

from __future__ import annotations

import asyncio
import re
import struct
from typing import Any, AsyncGenerator

import grpc
import grpc.aio
import httpx
from loguru import logger
from pipecat.frames.frames import (
    ErrorFrame,
    Frame,
    TTSAudioRawFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
)
from pipecat.services.ai_services import TTSService

from src.infrastructure.services.salute_auth import SaluteSpeechAuthManager
from src.infrastructure.voice.salute_grpc_tls import smartspeech_channel_credentials
from src.infrastructure.voice.sber_protos import synthesis_pb2, synthesis_pb2_grpc

# База REST SaluteSpeech (синтез в файл для MAX — только здесь; Pipecat остаётся на gRPC).
_DEFAULT_REST_V1_BASE = "https://smartspeech.sber.ru/rest/v1"


def _pcm16_mono_resample_linear(pcm: bytes, src_rate: int, dst_rate: int) -> bytes:
    """Линейный ресэмплинг int16 mono (без numpy/scipy)."""
    if src_rate <= 0 or dst_rate <= 0:
        logger.warning(
            "Ресэмплинг PCM: пропуск при некорректных частотах src_rate=%s dst_rate=%s",
            src_rate,
            dst_rate,
        )
        return pcm
    if src_rate == dst_rate or not pcm:
        return pcm
    n_in = len(pcm) // 2
    if n_in < 2:
        return pcm
    samples = struct.unpack(f"<{n_in}h", pcm)
    ratio = dst_rate / src_rate
    if ratio <= 0:
        return pcm
    n_out = max(1, int(n_in * ratio))
    out: list[int] = []
    for j in range(n_out):
        x = j / ratio
        i0 = int(x)
        i1 = min(i0 + 1, n_in - 1)
        frac = x - i0
        v = samples[i0] * (1.0 - frac) + samples[i1] * frac
        out.append(int(max(-32768, min(32767, round(v)))))
    return struct.pack(f"<{len(out)}h", *out)


def _infer_pcm_rate_from_voice(voice: str) -> int:
    """Эвристика: ``May_24000`` / ``Ost_24000`` → 24000 Гц."""
    m = re.search(r"_(\d{4,6})$", (voice or "").strip())
    if m:
        try:
            hz = int(m.group(1))
            if hz > 0:
                return hz
        except ValueError:
            pass
    return 24000


class SaluteSpeechTTSService(TTSService):
    """TTS: унарный ``Synthesize`` + поток ``SynthesisResponse.data`` (``grpc.aio``)."""

    def __init__(
        self,
        *,
        auth_manager: SaluteSpeechAuthManager,
        grpc_target: str = "smartspeech.sber.ru:443",
        voice: str = "Ost_24000",
        language: str = "ru-RU",
        smartspeech_verify_ssl: bool = True,
        rest_base_url: str | None = None,
        **kwargs: Any,
    ) -> None:
        # Pipecat TTSService: не даём передать sample_rate=0 (или другое) поверх нашей частоты выхода.
        kwargs.pop("sample_rate", None)
        super().__init__(sample_rate=24000, **kwargs)
        # sample_rate у TTSService в Pipecat — свойство без сеттера; при 0 используем _effective_output_sample_rate().
        self._auth = auth_manager
        self._grpc_target = grpc_target.strip()
        self.set_voice(voice)
        self._language = language
        self._verify_ssl = smartspeech_verify_ssl
        self._rest_base_url = (rest_base_url or _DEFAULT_REST_V1_BASE).strip().rstrip("/")
        self._api_pcm_rate = _infer_pcm_rate_from_voice(self._voice_id)
        self.set_model_name("salutespeech-tts-grpc")

    def _effective_output_sample_rate(self) -> int:
        """Целевая частота PCM после ресэмплинга (24000 Гц); если у родителя sample_rate некорректен — запасной 24000."""
        try:
            sr = int(self.sample_rate)
        except (TypeError, ValueError):
            sr = 0
        return sr if sr > 0 else 24000

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

    def _build_request(self, text: str) -> synthesis_pb2.SynthesisRequest:
        body = text if text.strip() else " "
        return synthesis_pb2.SynthesisRequest(
            text=body,
            audio_encoding=synthesis_pb2.SynthesisRequest.PCM_S16LE,
            language=self._language,
            content_type=synthesis_pb2.SynthesisRequest.TEXT,
            voice=self._voice_id,
            rebuild_cache=False,
        )

    async def run_tts(self, text: str) -> AsyncGenerator[Frame, None]:
        logger.debug("%s: SaluteSpeech TTS gRPC [%s…]", self, (text or "")[:80])
        token = await self._auth.get_access_token()
        req = self._build_request(text)
        creds = await self._get_channel_credentials()
        channel = grpc.aio.secure_channel(self._grpc_target, creds)
        stub = synthesis_pb2_grpc.SmartSpeechStub(channel)
        metadata = self._grpc_metadata(token)
        try:
            await self.start_ttfb_metrics()
            await self.start_tts_usage_metrics(text)
            first_audio = True
            async for resp in stub.Synthesize(req, metadata=metadata):
                raw = bytes(resp.data) if resp.data else b""
                if not raw:
                    continue
                out_sr = self._effective_output_sample_rate()
                pcm_out = _pcm16_mono_resample_linear(raw, self._api_pcm_rate, out_sr)
                if first_audio:
                    yield TTSStartedFrame()
                    first_audio = False
                await self.stop_ttfb_metrics()
                yield TTSAudioRawFrame(pcm_out, out_sr, num_channels=1)
            if first_audio:
                yield ErrorFrame("SaluteSpeech TTS: пустой поток аудио")
            else:
                yield TTSStoppedFrame()
        except grpc.aio.AioRpcError as err:
            if err.code() == grpc.StatusCode.UNAUTHENTICATED:
                await self._auth.invalidate_cache()
            logger.exception("SaluteSpeech TTS gRPC: {} {}", err.code(), err.details())
            yield ErrorFrame(f"SaluteSpeech TTS gRPC: {err.code()} {err.details()}")
        except Exception as exc:
            logger.exception("SaluteSpeech TTS gRPC: {}", exc)
            yield ErrorFrame(f"SaluteSpeech TTS: {exc}")
        finally:
            await channel.close()

    async def synthesize_to_file(self, text: str) -> bytes:
        """Синтез через **REST** ``text:synthesize`` → **Opus в OGG** (для MAX CDN; gRPC **run_tts** для Pipecat не трогаем).

        Формат ``format=opus`` — поддерживаемый REST SaluteSpeech (варианты ``mp3…`` дают HTTP 400).
        TLS: ``verify=self._verify_ssl`` (на VPS без корней Минцифры обычно ``false``, как в настройках SaluteSpeech).
        """
        body = (text or "").strip()
        if not body:
            return b""
        max_chars = 4000
        if len(body) > max_chars:
            logger.info("SaluteSpeech synthesize_to_file: текст усечён с %s до %s символов", len(body), max_chars)
            body = body[:max_chars]

        fmt = "opus"
        url = f"{self._rest_base_url}/text:synthesize?format={fmt}"

        token = await self._auth.get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/text",
        }
        timeout = httpx.Timeout(120.0, connect=30.0)

        async def _post(bearer: str) -> httpx.Response:
            h = {**headers, "Authorization": f"Bearer {bearer}"}
            async with httpx.AsyncClient(verify=self._verify_ssl, timeout=timeout, trust_env=False) as client:
                return await client.post(url, headers=h, content=body.encode("utf-8"))

        try:
            resp = await _post(token)
            if resp.status_code == 401:
                await self._auth.invalidate_cache()
                token = await self._auth.get_access_token()
                resp = await _post(token)
            if resp.status_code >= 400:
                logger.error(
                    "SaluteSpeech REST synthesize HTTP %s: %s",
                    resp.status_code,
                    (resp.text or "")[:500],
                )
                return b""
            data = resp.content
            if not data:
                logger.warning("SaluteSpeech synthesize_to_file: пустое тело ответа REST")
                return b""
            return data
        except httpx.HTTPError as exc:
            logger.exception("SaluteSpeech synthesize_to_file REST: {}", exc)
            return b""
        except Exception as exc:
            logger.exception("SaluteSpeech synthesize_to_file: {}", exc)
            return b""
