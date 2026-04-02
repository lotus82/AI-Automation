"""Буферизация PCM голосового диалога и сохранение стерео WAV (L — пользователь, R — бот)."""

from __future__ import annotations

import array
import re
import wave
from pathlib import Path

from loguru import logger
from pipecat.frames.frames import (
    AudioRawFrame,
    CancelFrame,
    Frame,
    InputAudioRawFrame,
    OutputAudioRawFrame,
    StartFrame,
    TTSAudioRawFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


def safe_recording_stem(session_id: str) -> str:
    """Имя файла без расширения: только безопасные символы (совпадает с UUID сессии)."""
    s = (session_id or "").strip()
    if re.fullmatch(r"[\da-fA-F-]{10,64}", s):
        return s
    return re.sub(r"[^\w.\-]", "_", s)[:64] or "unknown"


def recording_wav_basename(session_id: str) -> str:
    """Имя WAV в каталоге записей (для БД и аналитика)."""
    return f"{safe_recording_stem(session_id)}.wav"


def resolved_recording_file(base_dir: Path, stored_basename: str | None) -> Path | None:
    """Безопасное разрешение пути к WAV: только basename, без обхода каталога."""
    if not stored_basename:
        return None
    s = stored_basename.strip()
    if "/" in s or "\\" in s or ".." in s:
        return None
    name = Path(s).name
    if not name.endswith(".wav"):
        return None
    root = Path(base_dir).resolve()
    path = (root / name).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return None
    return path if path.is_file() else None


def _linear_resample_s16le(pcm: bytes, src_sr: int, dst_sr: int) -> bytes:
    if src_sr == dst_sr or not pcm:
        return pcm
    samples = array.array("h")
    samples.frombytes(pcm)
    if len(samples) < 2:
        return pcm
    ratio = dst_sr / src_sr
    new_len = max(1, int(len(samples) * ratio))
    out = array.array("h", [0] * new_len)
    for i in range(new_len):
        src_i = i / ratio
        j0 = int(src_i)
        j1 = min(j0 + 1, len(samples) - 1)
        frac = src_i - j0
        v = samples[j0] * (1 - frac) + samples[j1] * frac
        out[i] = int(max(-32768, min(32767, v)))
    return out.tobytes()


class ConversationStereoRecorder:
    """Накапливает моно PCM пользователя и бота, выравнивает по длине, пишет стерео 16 kHz."""

    def __init__(self, *, out_dir: Path, target_sample_rate: int = 16000) -> None:
        self._out_dir = Path(out_dir)
        self._target_sr = target_sample_rate
        self._user = bytearray()
        self._bot = bytearray()

    def append_user_pcm(self, pcm: bytes, sample_rate: int) -> None:
        if not pcm:
            return
        if sample_rate != self._target_sr:
            pcm = _linear_resample_s16le(pcm, sample_rate, self._target_sr)
        self._user.extend(pcm)

    def append_bot_pcm(self, pcm: bytes, sample_rate: int) -> None:
        if not pcm:
            return
        if sample_rate != self._target_sr:
            pcm = _linear_resample_s16le(pcm, sample_rate, self._target_sr)
        self._bot.extend(pcm)

    def write_wav_stereo(self, session_id: str) -> Path | None:
        u = bytes(self._user)
        b = bytes(self._bot)
        if not u and not b:
            return None
        stem = safe_recording_stem(session_id)
        self._out_dir.mkdir(parents=True, exist_ok=True)
        path = self._out_dir / f"{stem}.wav"
        nu = len(u) // 2
        nb = len(b) // 2
        n = max(nu, nb)
        if n == 0:
            return None
        u_pad = u + b"\x00" * (2 * (n - nu))
        b_pad = b + b"\x00" * (2 * (n - nb))
        interleaved = bytearray(4 * n)
        for i in range(n):
            interleaved[4 * i : 4 * i + 2] = u_pad[2 * i : 2 * i + 2]
            interleaved[4 * i + 2 : 4 * i + 4] = b_pad[2 * i : 2 * i + 2]
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(self._target_sr)
            wf.writeframes(bytes(interleaved))
        logger.info("Сохранена запись разговора: {} ({} сэмплов на канал)", path, n)
        return path


class UserAudioRecordingTap(FrameProcessor):
    """Перехват входящего аудио до STT."""

    def __init__(self, recorder: ConversationStereoRecorder, name: str | None = None) -> None:
        super().__init__(name=name)
        self._rec = recorder

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        if isinstance(frame, StartFrame):
            await self.push_frame(frame, direction)
            return
        if isinstance(frame, CancelFrame):
            await self.push_frame(frame, direction)
            return
        if direction == FrameDirection.DOWNSTREAM and isinstance(
            frame, (InputAudioRawFrame, AudioRawFrame)
        ):
            audio = getattr(frame, "audio", None) or b""
            sr = int(getattr(frame, "sample_rate", self._rec._target_sr))
            if audio:
                self._rec.append_user_pcm(audio, sr)
        await self.push_frame(frame, direction)


class BotAudioRecordingTap(FrameProcessor):
    """Перехват выхода TTS до транспорта (PCM бота)."""

    def __init__(self, recorder: ConversationStereoRecorder, name: str | None = None) -> None:
        super().__init__(name=name)
        self._rec = recorder

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        if isinstance(frame, StartFrame):
            await self.push_frame(frame, direction)
            return
        if isinstance(frame, CancelFrame):
            await self.push_frame(frame, direction)
            return
        if direction == FrameDirection.DOWNSTREAM and isinstance(
            frame, (TTSAudioRawFrame, OutputAudioRawFrame)
        ):
            audio = getattr(frame, "audio", None) or b""
            sr = int(getattr(frame, "sample_rate", 24000))
            if audio:
                self._rec.append_bot_pcm(audio, sr)
        await self.push_frame(frame, direction)
