"""Оркестрация голосового пайплайна Pipecat: STT → RAG (use case) → TTS."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Literal

import aiohttp
from loguru import logger
from pipecat.frames.frames import (
    CancelFrame,
    EndFrame,
    ErrorFrame,
    Frame,
    InterimTranscriptionFrame,
    StartFrame,
    StartInterruptionFrame,
    TranscriptionFrame,
    TTSSpeakFrame,
)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.services.deepgram import DeepgramSTTService
from pipecat.services.elevenlabs import ElevenLabsHttpTTSService
from pipecat.services.openai import OpenAITTSService
from pipecat.transcriptions.language import Language

from src.core.config import Settings
from src.domain.entities import TrainingScenario
from src.use_cases.interfaces import IVoiceTransport

# TODO: Вынести выбор модели Deepgram и маппинг языков в настройки при расширении локалей.


def _language_from_settings(code: str) -> Language:
    c = (code or "en").strip()
    try:
        return Language(c)
    except ValueError:
        logger.warning("Неизвестный VOICE_STT_LANGUAGE=%s, используется en", code)
        return Language.EN


class LLMUserResponseAggregator(FrameProcessor):
    """По финальной транскрипции вызывает сценарий ProcessTextMessageUseCase и отдаёт TTS."""

    def __init__(
        self,
        *,
        on_final_transcript: Callable[[str], Awaitable[str]],
        name: str | None = None,
    ) -> None:
        super().__init__(name=name)
        self._on_final = on_final_transcript
        self._turn_lock = asyncio.Lock()

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)

        if isinstance(frame, StartFrame):
            return
        if isinstance(frame, CancelFrame):
            return

        if isinstance(frame, TranscriptionFrame):
            text = (frame.text or "").strip()
            if text and direction == FrameDirection.DOWNSTREAM:
                async with self._turn_lock:
                    try:
                        reply = await self._on_final(text)
                        if reply.strip():
                            await self.push_frame(TTSSpeakFrame(reply.strip()))
                    except Exception as exc:  # noqa: BLE001 — логируем и продолжаем сессию
                        logger.exception("Ошибка RAG/LLM в голосовом агрегаторе: %s", exc)
                        await self.push_frame(
                            TTSSpeakFrame(
                                "Прошу прощения, произошла ошибка при обработке запроса. "
                                "Повторите, пожалуйста, вопрос чуть позже."
                            )
                        )
            return

        if isinstance(frame, InterimTranscriptionFrame):
            # Промежуточный текст не отправляем в консультанта и не пропускаем к TTS.
            return

        await self.push_frame(frame, direction)


class VoicePipelineOrchestrator:
    """Собирает Pipecat pipeline и связывает его с ProcessTextMessageUseCase."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _build_openai_tts(self) -> OpenAITTSService:
        if not self._settings.openai_api_key:
            raise ValueError("Для OpenAI TTS нужен OPENAI_API_KEY")
        return OpenAITTSService(
            api_key=self._settings.openai_api_key,
            voice=self._settings.openai_tts_voice,
            model=self._settings.openai_tts_model,
            sample_rate=OpenAITTSService.OPENAI_SAMPLE_RATE,
        )

    def _build_elevenlabs_tts(self, aiohttp_session: aiohttp.ClientSession) -> ElevenLabsHttpTTSService:
        key = self._settings.elevenlabs_api_key
        vid = self._settings.elevenlabs_voice_id
        if not key or not vid:
            raise ValueError(
                "Для VOICE_TTS_PROVIDER=elevenlabs нужны ELEVENLABS_API_KEY и ELEVENLABS_VOICE_ID"
            )
        return ElevenLabsHttpTTSService(
            api_key=key,
            voice_id=vid,
            aiohttp_session=aiohttp_session,
            sample_rate=24000,
        )

    async def _run_pipeline(
        self,
        *,
        voice_transport: IVoiceTransport,
        stt: DeepgramSTTService,
        aggregator: LLMUserResponseAggregator,
        tts: OpenAITTSService | ElevenLabsHttpTTSService,
    ) -> None:
        pipeline = Pipeline(
            [
                voice_transport.input_processor(),
                stt,
                aggregator,
                tts,
                voice_transport.output_processor(),
            ]
        )

        task = PipelineTask(
            pipeline,
            params=PipelineParams(
                audio_in_sample_rate=16000,
                audio_out_sample_rate=24000,
                allow_interruptions=True,
            ),
            idle_timeout_secs=None,
        )

        pt = voice_transport.pipecat_transport

        @stt.event_handler("on_speech_started")
        async def _on_speech_started(_service, *_args, **_kwargs) -> None:
            # Облачный VAD Deepgram: прерываем воспроизведение ответа бота.
            await task.queue_frame(StartInterruptionFrame())

        @pt.event_handler("on_client_disconnected")
        async def _on_client_disconnected(_transport, _websocket) -> None:
            await task.queue_frame(EndFrame())

        runner = PipelineRunner(handle_sigint=False)
        await runner.run(task)

    async def run(
        self,
        *,
        voice_transport: IVoiceTransport,
        on_final_transcript: Callable[[str], Awaitable[str]],
        voice_mode: Literal["consultant", "trainer_client"] = "consultant",
        training_scenario: TrainingScenario | None = None,
    ) -> None:
        """Запускает runner до завершения сессии (браузер: WebSocket; Asterisk: UDP RTP).

        Транспорт должен реализовать **IVoiceTransport** и иметь **pipecat_transport**
        с обработчиком **on_client_disconnected** (как FastAPI WebSocket и Asterisk RTP).
        """
        if voice_mode == "trainer_client" and training_scenario is not None:
            logger.info(
                "Голос: режим тренажёра (ИИ-клиент), сценарий id=%s, заголовок=%r",
                training_scenario.id,
                training_scenario.title[:120],
            )
        elif voice_mode == "consultant":
            logger.debug("Голос: режим консультанта (ИИ-продавец)")

        if not self._settings.deepgram_api_key:
            raise ValueError("Для голоса нужен DEEPGRAM_API_KEY")

        from deepgram import LiveOptions

        lang = _language_from_settings(self._settings.voice_stt_language)
        live_options = LiveOptions(
            vad_events=True,
            language=lang,
            interim_results=True,
            smart_format=True,
            punctuate=True,
            model="nova-2-general",
        )

        stt = DeepgramSTTService(
            api_key=self._settings.deepgram_api_key,
            live_options=live_options,
        )

        aggregator = LLMUserResponseAggregator(on_final_transcript=on_final_transcript)

        if self._settings.voice_tts_provider == "elevenlabs":
            async with aiohttp.ClientSession() as http_session:
                tts = self._build_elevenlabs_tts(http_session)
                await self._run_pipeline(
                    voice_transport=voice_transport,
                    stt=stt,
                    aggregator=aggregator,
                    tts=tts,
                )
        else:
            tts = self._build_openai_tts()
            await self._run_pipeline(
                voice_transport=voice_transport,
                stt=stt,
                aggregator=aggregator,
                tts=tts,
            )
