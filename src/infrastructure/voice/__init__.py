"""Инфраструктура голоса (Pipecat)."""

from src.infrastructure.voice.processor import VoicePipelineOrchestrator
from src.infrastructure.voice.transport import PipecatWebSocketVoiceTransport

__all__ = ["PipecatWebSocketVoiceTransport", "VoicePipelineOrchestrator"]
