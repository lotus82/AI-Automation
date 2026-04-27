"""TTS T-Bank VoiceKit (gRPC StreamingSynthesize), 24 kHz LINEAR16 — как Salute TTS в пайплайне."""

from __future__ import annotations

from typing import Any, AsyncGenerator

import grpc
import grpc.aio
from loguru import logger
from pipecat.frames.frames import (
    ErrorFrame,
    Frame,
    TTSAudioRawFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
)
from pipecat.services.ai_services import TTSService

import src.infrastructure.voice.tbank_tinkoff_imports  # noqa: F401
from tinkoff.cloud.tts.v1 import tts_pb2, tts_pb2_grpc

from src.infrastructure.voice.tbank_voicekit_auth import authorization_metadata
from src.infrastructure.voice.tbank_voicekit_config import TbankVoiceKitCredentials

_SCOPE_TTS = "tinkoff.cloud.tts"
_OUT_HZ = 24000


class TbankVoiceKitTTSService(TTSService):
    def __init__(
        self,
        *,
        credentials: TbankVoiceKitCredentials,
        voice: str = "filipp",
        **kwargs: Any,
    ) -> None:
        kwargs.pop("sample_rate", None)
        super().__init__(sample_rate=_OUT_HZ, **kwargs)
        self._creds = credentials
        self._voice = (voice or "filipp").strip()
        self.set_model_name("tbank-voicekit-tts")

    def can_generate_metrics(self) -> bool:
        return True

    def _build_request(self, text: str) -> tts_pb2.SynthesizeSpeechRequest:
        body = (text or "").strip() or " "
        return tts_pb2.SynthesizeSpeechRequest(
            input=tts_pb2.SynthesisInput(text=body),
            voice=tts_pb2.VoiceSelectionParams(name=self._voice),
            audio_config=tts_pb2.AudioConfig(
                audio_encoding=tts_pb2.LINEAR16,
                sample_rate_hertz=_OUT_HZ,
            ),
        )

    async def run_tts(self, text: str) -> AsyncGenerator[Frame, None]:
        logger.debug("T-Bank TTS: [%s…]", (text or "")[:80])
        req = self._build_request(text)
        metadata = authorization_metadata(
            self._creds.api_key, self._creds.secret_key, _SCOPE_TTS, as_type=list
        )
        ch = grpc.aio.secure_channel(self._creds.grpc_target, grpc.ssl_channel_credentials())
        try:
            stub = tts_pb2_grpc.TextToSpeechStub(ch)
            await self.start_ttfb_metrics()
            await self.start_tts_usage_metrics(text)
            first = True
            call = stub.StreamingSynthesize(req, metadata=metadata)
            async for part in call:
                raw = bytes(part.audio_chunk) if part.audio_chunk else b""
                if not raw:
                    continue
                if first:
                    yield TTSStartedFrame()
                    first = False
                await self.stop_ttfb_metrics()
                yield TTSAudioRawFrame(raw, _OUT_HZ, num_channels=1)
            if first:
                yield ErrorFrame("T-Bank TTS: пустой ответ")
            else:
                yield TTSStoppedFrame()
        except grpc.aio.AioRpcError as err:
            logger.exception("T-Bank TTS gRPC: {} {}", err.code(), err.details())
            yield ErrorFrame(f"T-Bank TTS: {err.code()} {err.details()}")
        except Exception as exc:
            logger.exception("T-Bank TTS: {}", exc)
            yield ErrorFrame(f"T-Bank TTS: {exc}")
        finally:
            await ch.close()
