"""REST-клиент T-Bank VoiceKit (T-API): распознавание и синтез (альтернатива/диагностика gRPC)."""

from __future__ import annotations

import base64
from typing import Any

import httpx
from google.protobuf.json_format import MessageToDict
from loguru import logger

import src.infrastructure.voice.tbank_tinkoff_imports  # noqa: F401
from tinkoff.cloud.stt.v1 import stt_pb2
from tinkoff.cloud.tts.v1 import tts_pb2

from src.infrastructure.voice.tbank_voicekit_auth import authorization_metadata
from src.infrastructure.voice.tbank_voicekit_config import TbankVoiceKitCredentials, normalize_tbank_grpc_target


def _rest_base_from_target(grpc_target: str) -> str:
    t = (grpc_target or "").strip() or "api.tinkoff.ai:443"
    if t.endswith(":443"):
        host = t.rsplit(":", 1)[0]
        return f"https://{host}"
    if t.endswith(":80"):
        host = t.rsplit(":", 1)[0]
        return f"http://{host}"
    return f"https://{t.split(':', 1)[0]}"


class TbankVoiceKitRestClient:
    """См. `recognize_rest.py` / `tts_list_voices_rest.py` в voicekit-examples: HTTP/2 + JWT."""

    def __init__(self, credentials: TbankVoiceKitCredentials) -> None:
        self._c = credentials
        self._base = _rest_base_from_target(credentials.grpc_target)

    @property
    def base_url(self) -> str:
        return self._base

    async def recognize_json(
        self,
        *,
        audio_linear16: bytes,
        language_code: str = "ru-RU",
        sample_rate_hertz: int = 16000,
    ) -> dict[str, Any] | None:
        """``POST /v1/stt:recognize`` — нестримовое, целиком в теле (JSON)."""
        req = stt_pb2.RecognizeRequest()
        req.config.encoding = stt_pb2.AudioEncoding.LINEAR16
        req.config.sample_rate_hertz = int(sample_rate_hertz)
        req.config.num_channels = 1
        req.config.language_code = (language_code or "ru-RU").strip()
        req.config.enable_automatic_punctuation = True
        req.audio.content = audio_linear16
        body = MessageToDict(
            req,
            preserving_proto_field_name=True,
        )
        headers = authorization_metadata(
            self._c.api_key,
            self._c.secret_key,
            "tinkoff.cloud.stt",
            as_type=dict,
        )
        try:
            async with httpx.AsyncClient(http2=True, timeout=httpx.Timeout(120.0, connect=30.0)) as client:
                r = await client.post(
                    f"{self._base}/v1/stt:recognize",
                    json=body,
                    headers=headers,
                )
        except httpx.HTTPError as exc:
            logger.exception("T-Bank STT REST: %s", exc)
            return None
        if r.status_code != 200:
            logger.error("T-Bank STT REST HTTP %s: %s", r.status_code, (r.text or "")[:800])
            return None
        return r.json()

    async def synthesize_json(
        self,
        text: str,
        *,
        voice: str = "filipp",
        sample_rate_hertz: int = 24000,
    ) -> bytes | None:
        """``POST /v1/tts:synthesize`` — унарный JSON-ответ (audio_content)."""
        req = tts_pb2.SynthesizeSpeechRequest(
            input=tts_pb2.SynthesisInput(text=(text or " ").strip() or " "),
            voice=tts_pb2.VoiceSelectionParams(name=voice),
            audio_config=tts_pb2.AudioConfig(
                audio_encoding=tts_pb2.LINEAR16,
                sample_rate_hertz=sample_rate_hertz,
            ),
        )
        body = MessageToDict(
            req,
            preserving_proto_field_name=True,
        )
        headers = authorization_metadata(
            self._c.api_key,
            self._c.secret_key,
            "tinkoff.cloud.tts",
            as_type=dict,
        )
        try:
            async with httpx.AsyncClient(http2=True, timeout=httpx.Timeout(120.0, connect=30.0)) as client:
                r = await client.post(
                    f"{self._base}/v1/tts:synthesize",
                    json=body,
                    headers=headers,
                )
        except httpx.HTTPError as exc:
            logger.exception("T-Bank TTS REST: %s", exc)
            return None
        if r.status_code != 200:
            logger.error("T-Bank TTS REST HTTP %s: %s", r.status_code, (r.text or "")[:800])
            return None
        data = r.json()
        b64 = data.get("audioContent") or data.get("audio_content")
        if not b64 or not isinstance(b64, str):
            return None
        try:
            return base64.b64decode(b64)
        except Exception:
            return None

    async def list_voices(self) -> dict[str, Any] | None:
        """``GET /v1/tts:list_voices``."""
        headers = authorization_metadata(
            self._c.api_key,
            self._c.secret_key,
            "tinkoff.cloud.tts",
            as_type=dict,
        )
        try:
            async with httpx.AsyncClient(http2=True, timeout=httpx.Timeout(30.0, connect=10.0)) as client:
                r = await client.get(
                    f"{self._base}/v1/tts:list_voices",
                    headers=headers,
                )
        except httpx.HTTPError as exc:
            logger.exception("T-Bank TTS list_voices: %s", exc)
            return None
        if r.status_code != 200:
            return None
        return r.json()

