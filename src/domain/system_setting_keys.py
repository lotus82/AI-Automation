"""Имена ключей динамических настроек (БД + Redis-кэш)."""

from __future__ import annotations

# Ключи строк в таблице system_settings
LLM_PROVIDER = "LLM_PROVIDER"
DEEPSEEK_API_KEY = "DEEPSEEK_API_KEY"
OPENAI_API_KEY = "OPENAI_API_KEY"
TELEGRAM_BOT_TOKEN = "TELEGRAM_BOT_TOKEN"
DEFAULT_CONSULTANT_PROMPT = "DEFAULT_CONSULTANT_PROMPT"
ANALYST_QA_PROMPT = "ANALYST_QA_PROMPT"
SALUTESPEECH_AUTH_KEY = "SALUTESPEECH_AUTH_KEY"
SALUTESPEECH_SCOPE = "SALUTESPEECH_SCOPE"
SALUTESPEECH_VOICE = "SALUTESPEECH_VOICE"

# Разрешённые к обновлению через API (безопасность)
UPDATABLE_KEYS = frozenset(
    {
        LLM_PROVIDER,
        DEEPSEEK_API_KEY,
        OPENAI_API_KEY,
        TELEGRAM_BOT_TOKEN,
        DEFAULT_CONSULTANT_PROMPT,
        ANALYST_QA_PROMPT,
        SALUTESPEECH_AUTH_KEY,
        SALUTESPEECH_SCOPE,
        SALUTESPEECH_VOICE,
    }
)

# Ключи, значения которых маскируются в GET /api/settings
SECRET_VALUE_KEYS = frozenset(
    {
        DEEPSEEK_API_KEY,
        OPENAI_API_KEY,
        TELEGRAM_BOT_TOKEN,
        SALUTESPEECH_AUTH_KEY,
    }
)
