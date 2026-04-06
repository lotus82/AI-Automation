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
# «1»/«true» — разрешить инструмент search_web в текстовом чате и голосе (консультант)
ENABLE_WEB_SEARCH = "ENABLE_WEB_SEARCH"
# Температура сэмплирования для чата консультанта и generate_response (расписание): строка с float 0.0–1.0
LLM_TEMPERATURE = "LLM_TEMPERATURE"
# «1»/«true» — после текстового ответа в MAX отправлять озвучку (SaluteSpeech → WAV → uploads → audio)
MAX_VOICE_REPLY_ENABLED = "MAX_VOICE_REPLY_ENABLED"
# Задержка «снятия трубки» для входящего VoIP-звонка MAX (секунды, целое число)
MAX_CALL_ANSWER_DELAY = "MAX_CALL_ANSWER_DELAY"
# Первая фраза голосового пайплайна после ответа на звонок (до первого запроса к LLM)
MAX_CALL_GREETING_PHRASE = "MAX_CALL_GREETING_PHRASE"

# Разрешённые к обновлению через API (безопасность)
UPDATABLE_KEYS = frozenset(
    {
        LLM_PROVIDER,
        LLM_TEMPERATURE,
        MAX_VOICE_REPLY_ENABLED,
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
        ENABLE_WEB_SEARCH,
        MAX_CALL_ANSWER_DELAY,
        MAX_CALL_GREETING_PHRASE,
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
