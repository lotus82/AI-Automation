"""Имена ключей динамических настроек (БД + Redis-кэш)."""

from __future__ import annotations

# Ключи строк в таблице system_settings
LLM_PROVIDER = "LLM_PROVIDER"
DEEPSEEK_API_KEY = "DEEPSEEK_API_KEY"
OPENAI_API_KEY = "OPENAI_API_KEY"
TELEGRAM_BOT_TOKEN = "TELEGRAM_BOT_TOKEN"
DEFAULT_CONSULTANT_PROMPT = "DEFAULT_CONSULTANT_PROMPT"
# Дополнение к system-сообщению для MAX/Telegram (формат текста ответа); не используется в голосе.
TEXT_BOT_SYSTEM_SUPPLEMENT = "TEXT_BOT_SYSTEM_SUPPLEMENT"
ANALYST_QA_PROMPT = "ANALYST_QA_PROMPT"
SALUTESPEECH_AUTH_KEY = "SALUTESPEECH_AUTH_KEY"
SALUTESPEECH_SCOPE = "SALUTESPEECH_SCOPE"
SALUTESPEECH_VOICE = "SALUTESPEECH_VOICE"
MAX_BOT_TOKEN = "MAX_BOT_TOKEN"
MAX_CONTEXT_LIMIT = "MAX_CONTEXT_LIMIT"
# «1»/«true» — опрос GET /updates; «0»/«false» — не дергать API (Webhook или пауза)
MAX_USE_POLLING = "MAX_USE_POLLING"
# Подстрока упоминания в группе (например @id…_bot); в группах без неё входящие не обрабатываются.
MAX_BOT_USERNAME = "MAX_BOT_USERNAME"
# Совпадение session_id (str(chat_id)) — подмешивание MAX_GROUP_ADDITIONAL_PROMPT к системному промпту.
MAX_GROUP_CHAT_ID = "MAX_GROUP_CHAT_ID"
MAX_GROUP_ADDITIONAL_PROMPT = "MAX_GROUP_ADDITIONAL_PROMPT"

# Разрешённые к обновлению через API (безопасность)
UPDATABLE_KEYS = frozenset(
    {
        LLM_PROVIDER,
        DEEPSEEK_API_KEY,
        OPENAI_API_KEY,
        TELEGRAM_BOT_TOKEN,
        DEFAULT_CONSULTANT_PROMPT,
        TEXT_BOT_SYSTEM_SUPPLEMENT,
        ANALYST_QA_PROMPT,
        SALUTESPEECH_AUTH_KEY,
        SALUTESPEECH_SCOPE,
        SALUTESPEECH_VOICE,
        MAX_BOT_TOKEN,
        MAX_CONTEXT_LIMIT,
        MAX_USE_POLLING,
        MAX_BOT_USERNAME,
        MAX_GROUP_CHAT_ID,
        MAX_GROUP_ADDITIONAL_PROMPT,
    }
)

# Ключи, значения которых маскируются в GET /api/settings
SECRET_VALUE_KEYS = frozenset(
    {
        DEEPSEEK_API_KEY,
        OPENAI_API_KEY,
        TELEGRAM_BOT_TOKEN,
        SALUTESPEECH_AUTH_KEY,
        MAX_BOT_TOKEN,
    }
)
