"""Обратная совместимость: основная реализация — **DynamicLLMService** в dynamic_llm.py.

История чата в LLM уходит списком сообщений с полями ``role`` и ``content`` (без склейки истории в одну строку);
сборка — в ``ProcessTextMessageUseCase`` и ``memory_history_to_openai_messages`` (фаза 20).

Текстовый канал MAX (группы): дополнительный системный контекст для выбранного ``chat_id``
собирается в ``ProcessTextMessageUseCase`` (ключи **MAX_GROUP_CHAT_ID** / **MAX_GROUP_ADDITIONAL_PROMPT**)
и передаётся в первом сообщении ``role=system`` в ``generate_sales_response_with_tools`` — см. фазу 17.

Инструменты чата объявляются в ``src/use_cases/chat.py`` (``record_lead``, ``search_web`` при **ENABLE_WEB_SEARCH**) —
см. фазу 19 (веб-поиск DuckDuckGo).

Температура сэмплирования для диалога консультанта задаётся ключом **LLM_TEMPERATURE** в настройках (читает
``DynamicLLMService._resolve_chat_temperature``, фаза 21); аналитика JSON (ОКК, тренер) использует **temperature=0.0**.
"""

from src.infrastructure.services.dynamic_llm import DynamicLLMService

# Старое имя класса (до фазы 12).
OpenAILLMService = DynamicLLMService

__all__ = ["DynamicLLMService", "OpenAILLMService"]
