"""Оркестрация голосового пайплайна Pipecat: STT → RAG (use case) → TTS."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

# Колбэк для реплики до основного ответа (например фраза «ищу в интернете» при search_web).
IntermediateTTSCallback = Callable[[str], Awaitable[None]]
# STT → сценарий: второй аргумент — отправка промежуточной фразы в TTS (Pipecat).
FinalTranscriptHandler = Callable[[str, IntermediateTTSCallback], Awaitable[str]]
from pathlib import Path
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
from src.core.utils.text_cleaner import remove_markdown
from src.domain.entities import TrainingScenario
from src.infrastructure.services.salute_auth import SaluteSpeechAuthManager
from src.infrastructure.voice.conversation_recording import (
    BotAudioRecordingTap,
    ConversationStereoRecorder,
    UserAudioRecordingTap,
)
from src.infrastructure.voice.salute_stt import SaluteSpeechSTTService
from src.infrastructure.voice.salute_tts import SaluteSpeechTTSService
from src.use_cases.interfaces import IVoiceTransport

# TODO: Вынести выбор модели Deepgram и маппинг языков в настройки при расширении локалей.


def _language_from_settings(code: str) -> Language:
    c = (code or "en").strip()
    try:
        return Language(c)
    except ValueError:
        logger.warning("Неизвестный VOICE_STT_LANGUAGE=%s, используется en", code)
        return Language.EN


def _salute_language_tag_from_voice_stt(code: str) -> str:
    """RFC-3066 тег для SaluteSpeech (упрощённый маппинг из VOICE_STT_LANGUAGE)."""
    c = (code or "ru").strip().lower().replace("_", "-")
    if c.startswith("ru"):
        return "ru-RU"
    if c.startswith("en"):
        return "en-US"
    return "ru-RU"


class LLMUserResponseAggregator(FrameProcessor):
    """По финальной транскрипции вызывает сценарий ProcessTextMessageUseCase и отдаёт TTS."""

    def __init__(
        self,
        *,
        on_final_transcript: FinalTranscriptHandler,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name)
        self._on_final = on_final_transcript
        self._turn_lock = asyncio.Lock()

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)

        # Pipecat 0.0.60: FrameProcessor.process_frame(StartFrame) только инициализирует
        # процессор и не вызывает push_frame вниз. Без явной пересылки TTS не получает
        # StartFrame → не создаётся __input_queue → при EndFrame падает queue_frame.
        if isinstance(frame, StartFrame):
            await self.push_frame(frame, direction)
            return
        if isinstance(frame, CancelFrame):
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, TranscriptionFrame):
            text = (frame.text or "").strip()
            if text and direction == FrameDirection.DOWNSTREAM:
                # Отдаём финальную транскрипцию на WebSocket-клиент (Protobuf transcription).
                await self.push_frame(frame, direction)
                async with self._turn_lock:
                    try:

                        async def push_intermediate_tts(spoken: str) -> None:
                            # В Pipecat 0.0.60 для озвучки текста используется TTSSpeakFrame (см. также TTSTextFrame в новых версиях).
                            clean_i = remove_markdown((spoken or "").strip())
                            if clean_i:
                                await self.push_frame(TTSSpeakFrame(clean_i))

                        reply = await self._on_final(text, push_intermediate_tts)
                        # Дубль очистки: сценарий уже санитизирует ответ; на случай других колбэков.
                        clean = remove_markdown((reply or "").strip())
                        if clean:
                            await self.push_frame(TTSSpeakFrame(clean))
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
        stt: DeepgramSTTService | SaluteSpeechSTTService,
        aggregator: LLMUserResponseAggregator,
        tts: OpenAITTSService | ElevenLabsHttpTTSService | SaluteSpeechTTSService,
        stereo_recorder: ConversationStereoRecorder | None = None,
        fixed_greeting_phrase: str | None = None,
    ) -> None:
        if stereo_recorder is not None:
            user_tap = UserAudioRecordingTap(stereo_recorder, name="user_recording")
            bot_tap = BotAudioRecordingTap(stereo_recorder, name="bot_recording")
            processors = [
                voice_transport.input_processor(),
                user_tap,
                stt,
                aggregator,
                tts,
                bot_tap,
                voice_transport.output_processor(),
            ]
        else:
            processors = [
                voice_transport.input_processor(),
                stt,
                aggregator,
                tts,
                voice_transport.output_processor(),
            ]
        pipeline = Pipeline(processors)

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
            # Deepgram VAD или первый частичный гипотеза SaluteSpeech — прерываем ответ бота.
            await task.queue_frame(StartInterruptionFrame())

        @pt.event_handler("on_client_disconnected")
        async def _on_client_disconnected(_transport, _websocket) -> None:
            await task.queue_frame(EndFrame())

        runner = PipelineRunner(handle_sigint=False)
        run_co = asyncio.create_task(runner.run(task))
        greet = (fixed_greeting_phrase or "").strip()
        if greet:
            clean_g = remove_markdown(greet)
            if clean_g:
                # Небольшая пауза, чтобы пайплайн принял StartFrame до первой реплики TTS.
                # TODO (рус.): при смене версии Pipecat проверить порядок кадров (TTSSpeakFrame / TTSTextFrame).
                await asyncio.sleep(0.12)
                try:
                    await task.queue_frame(TTSSpeakFrame(clean_g))
                except Exception:
                    logger.exception("Не удалось поставить фиксированное приветствие в очередь пайплайна")
        await run_co

    async def run(
        self,
        *,
        voice_transport: IVoiceTransport,
        on_final_transcript: FinalTranscriptHandler,
        voice_mode: Literal["consultant", "trainer_client"] = "consultant",
        training_scenario: TrainingScenario | None = None,
        salute_auth: SaluteSpeechAuthManager | None = None,
        salutespeech_voice: str | None = None,
        voice_stt_provider_effective: str | None = None,
        recording_session_id: str | None = None,
        fixed_greeting_phrase: str | None = None,
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

        stt_sel = (voice_stt_provider_effective or self._settings.voice_stt_provider).strip().lower()
        if stt_sel not in ("deepgram", "salutespeech"):
            stt_sel = self._settings.voice_stt_provider

        uses_salute = stt_sel == "salutespeech" or self._settings.voice_tts_provider == "salutespeech"
        auth: SaluteSpeechAuthManager | None = salute_auth
        if uses_salute:
            if auth is None:
                raise ValueError(
                    "SaluteSpeech: передайте salute_auth (менеджер токенов с Redis) в VoicePipelineOrchestrator.run"
                )
            await auth.prewarm()

        if stt_sel == "salutespeech":
            assert auth is not None
            stt = SaluteSpeechSTTService(
                auth_manager=auth,
                grpc_target=self._settings.salutespeech_grpc_target,
                language=_salute_language_tag_from_voice_stt(self._settings.voice_stt_language),
                smartspeech_verify_ssl=self._settings.salutespeech_smartspeech_verify_ssl,
                sample_rate=16000,
            )
        else:
            if not (self._settings.deepgram_api_key or "").strip():
                raise ValueError("Для голоса с Deepgram нужен DEEPGRAM_API_KEY")

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

        voice_id = (salutespeech_voice or self._settings.salutespeech_voice or "Ost_24000").strip()

        stereo_recorder: ConversationStereoRecorder | None = None
        rec_dir = self._settings.call_recordings_dir
        if rec_dir and recording_session_id:
            stereo_recorder = ConversationStereoRecorder(
                out_dir=Path(rec_dir),
                target_sample_rate=16000,
            )

        if self._settings.voice_tts_provider == "salutespeech":
            assert auth is not None
            tts = SaluteSpeechTTSService(
                auth_manager=auth,
                grpc_target=self._settings.salutespeech_grpc_target,
                voice=voice_id,
                smartspeech_verify_ssl=self._settings.salutespeech_smartspeech_verify_ssl,
                rest_base_url=self._settings.salutespeech_rest_base_url,
            )
            await self._run_pipeline(
                voice_transport=voice_transport,
                stt=stt,
                aggregator=aggregator,
                tts=tts,
                stereo_recorder=stereo_recorder,
                fixed_greeting_phrase=fixed_greeting_phrase,
            )
        elif self._settings.voice_tts_provider == "elevenlabs":
            async with aiohttp.ClientSession() as http_session:
                tts = self._build_elevenlabs_tts(http_session)
                await self._run_pipeline(
                    voice_transport=voice_transport,
                    stt=stt,
                    aggregator=aggregator,
                    tts=tts,
                    stereo_recorder=stereo_recorder,
                    fixed_greeting_phrase=fixed_greeting_phrase,
                )
        else:
            tts = self._build_openai_tts()
            await self._run_pipeline(
                voice_transport=voice_transport,
                stt=stt,
                aggregator=aggregator,
                tts=tts,
                stereo_recorder=stereo_recorder,
                fixed_greeting_phrase=fixed_greeting_phrase,
            )

        if stereo_recorder is not None and recording_session_id:
            stereo_recorder.write_wav_stereo(recording_session_id)
