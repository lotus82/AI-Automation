"""Обратная совместимость: основная реализация — **DynamicLLMService** в dynamic_llm.py."""

from src.infrastructure.services.dynamic_llm import DynamicLLMService

# Старое имя класса (до фазы 12).
OpenAILLMService = DynamicLLMService

__all__ = ["DynamicLLMService", "OpenAILLMService"]
