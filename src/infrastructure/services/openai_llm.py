"""Обратная совместимость: основная реализация — **DynamicLLMService** в dynamic_llm.py.

Текстовый канал MAX (группы): дополнительный системный контекст для выбранного ``chat_id``
собирается в ``ProcessTextMessageUseCase`` (ключи **MAX_GROUP_CHAT_ID** / **MAX_GROUP_ADDITIONAL_PROMPT**)
и передаётся в первом сообщении ``role=system`` в ``generate_sales_response_with_tools`` — см. фазу 17.
"""

from src.infrastructure.services.dynamic_llm import DynamicLLMService

# Старое имя класса (до фазы 12).
OpenAILLMService = DynamicLLMService

__all__ = ["DynamicLLMService", "OpenAILLMService"]
