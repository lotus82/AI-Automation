"""Управление конфигурацией через Pydantic Settings."""

from datetime import datetime
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения, загружаемые из переменных окружения и .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Окружение и режим отладки
    app_env: str = Field(default="development", validation_alias="APP_ENV")
    app_debug: bool = Field(default=False, validation_alias="APP_DEBUG")
    # Часовой пояс пользователей и групповых чатов (IANA), например Саратов UTC+4
    app_timezone: str = Field(
        default="Europe/Saratov",
        validation_alias="APP_TIMEZONE",
        description="IANA TZ для бизнес-логики, Celery Beat и подсказок LLM о текущем времени.",
    )

    # Инфраструктура
    postgres_uri: str = Field(
        default="postgresql+asyncpg://sales:sales@localhost:5432/sales_agent",
        validation_alias="POSTGRES_URI",
    )
    redis_uri: str = Field(
        default="redis://localhost:6379/0",
        validation_alias="REDIS_URI",
    )

    # Celery (отдельные номера БД Redis от приложения, чтобы не смешивать ключи с чатом)
    celery_broker_url: str = Field(
        default="redis://localhost:6379/1",
        validation_alias="CELERY_BROKER_URL",
    )
    celery_result_backend: str = Field(
        default="redis://localhost:6379/2",
        validation_alias="CELERY_RESULT_BACKEND",
    )

    # TTL истории диалога в Redis (секунды)
    chat_memory_ttl_seconds: int = Field(
        default=86400,
        ge=60,
        validation_alias="CHAT_MEMORY_TTL_SECONDS",
    )

    # OpenAI (эмбеддинги и чат; опционально — без ключа работают заглушки в адаптерах)
    openai_api_key: str | None = Field(
        default=None,
        validation_alias="OPENAI_API_KEY",
    )
    # Fallback, если ключ ещё не сохранён в system_settings (панель «Настройки»)
    deepseek_api_key: str | None = Field(
        default=None,
        validation_alias="DEEPSEEK_API_KEY",
    )
    telegram_bot_token: str | None = Field(
        default=None,
        validation_alias="TELEGRAM_BOT_TOKEN",
    )

    # Устарело для запуска воркера: задача long poll всегда создаётся в lifespan; вкл/выкл — MAX_USE_POLLING в БД.
    max_use_polling: bool = Field(default=True, validation_alias="MAX_USE_POLLING")
    max_platform_api_base: str = Field(
        default="https://platform-api.max.ru",
        validation_alias="MAX_PLATFORM_API_BASE",
    )
    max_api_base: str = Field(
        default="https://api.max.ru",
        validation_alias="MAX_API_BASE",
    )
    # Fallback, если токен не задан в system_settings (панель «Настройки»)
    max_bot_token: str | None = Field(
        default=None,
        validation_alias="MAX_BOT_TOKEN",
    )

    # Голос: облачный STT/TTS (без локальных моделей)
    deepgram_api_key: str | None = Field(
        default=None,
        validation_alias="DEEPGRAM_API_KEY",
    )
    elevenlabs_api_key: str | None = Field(
        default=None,
        validation_alias="ELEVENLABS_API_KEY",
    )
    elevenlabs_voice_id: str | None = Field(
        default=None,
        validation_alias="ELEVENLABS_VOICE_ID",
    )
    # Провайдер синтеза: openai | elevenlabs | salutespeech (без локального TTS)
    voice_tts_provider: str = Field(
        default="openai",
        validation_alias="VOICE_TTS_PROVIDER",
    )
    openai_tts_voice: str = Field(
        default="alloy",
        validation_alias="OPENAI_TTS_VOICE",
    )
    openai_tts_model: str = Field(
        default="gpt-4o-mini-tts",
        validation_alias="OPENAI_TTS_MODEL",
    )
    # Язык распознавания Deepgram (код ISO; в Pipecat передаётся как Language)
    voice_stt_language: str = Field(
        default="ru",
        validation_alias="VOICE_STT_LANGUAGE",
    )
    # STT: deepgram | salutespeech (SaluteSpeech — gRPC Recognize, поток PCM)
    voice_stt_provider: str = Field(
        default="deepgram",
        validation_alias="VOICE_STT_PROVIDER",
    )

    # SaluteSpeech (Сбер SmartSpeech): OAuth через ngw + токен в Redis (см. фаза 13 README)
    salutespeech_auth_key: str | None = Field(
        default=None,
        validation_alias="SALUTESPEECH_AUTH_KEY",
    )
    salutespeech_scope: str = Field(
        default="SALUTE_SPEECH_PERS",
        validation_alias="SALUTESPEECH_SCOPE",
    )
    salutespeech_voice: str = Field(
        default="Ost_24000",
        validation_alias="SALUTESPEECH_VOICE",
    )
    salutespeech_ws_recognize_url: str = Field(
        default="wss://smartspeech.sber.ru/async/recognize",
        validation_alias="SALUTESPEECH_WS_RECOGNIZE_URL",
        description="Устарело: STT/TTS SaluteSpeech — только gRPC (см. SALUTESPEECH_GRPC_TARGET).",
    )
    salutespeech_rest_base_url: str = Field(
        default="https://smartspeech.sber.ru/rest/v1/",
        validation_alias="SALUTESPEECH_REST_BASE_URL",
        description="База REST SaluteSpeech: **text:synthesize** (Opus для MAX); STT/TTS в звонке — gRPC.",
    )
    salutespeech_grpc_target: str = Field(
        default="smartspeech.sber.ru:443",
        validation_alias="SALUTESPEECH_GRPC_TARGET",
        description="Хост:порт gRPC SaluteSpeech (TLS). В документации часто 443; при необходимости укажите :8443.",
    )
    # OAuth SaluteSpeech (HTTP POST); при блокировке 9443 / DPI — прокси или другой URL из документации Сбера
    salutespeech_oauth_url: str = Field(
        default="https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
        validation_alias="SALUTESPEECH_OAUTH_URL",
    )
    salutespeech_oauth_retries: int = Field(
        default=3,
        ge=1,
        le=10,
        validation_alias="SALUTESPEECH_OAUTH_RETRIES",
    )
    # true — учитывать HTTP(S)_PROXY из окружения (нужно за корпоративным прокси); false — типично для Docker Desktop
    salutespeech_oauth_trust_env: bool = Field(
        default=False,
        validation_alias="SALUTESPEECH_OAUTH_TRUST_ENV",
    )
    # TLS при обмене ключа на OAuth-шлюз (часто нужен корневой Минцифры на VPS)
    salutespeech_oauth_verify_ssl: bool = Field(
        default=False,
        validation_alias="SALUTESPEECH_OAUTH_VERIFY_SSL",
    )
    # TLS к smartspeech.sber.ru: false — для gRPC доверяем листовому сертификату (как verify=False у httpx)
    salutespeech_smartspeech_verify_ssl: bool = Field(
        default=False,
        validation_alias="SALUTESPEECH_SMARTSPEECH_VERIFY_SSL",
    )

    # Bitrix24: полный URL входящего вебхука для crm.lead.add
    bitrix24_webhook_url: str | None = Field(
        default=None,
        validation_alias="BITRIX24_WEBHOOK_URL",
    )

    # SIP (транк MCN.ru / Asterisk / FreeSWITCH) — без локальных кодеков в приложении
    sip_server_ip: str | None = Field(
        default=None,
        validation_alias="SIP_SERVER_IP",
    )
    sip_user: str | None = Field(
        default=None,
        validation_alias="SIP_USER",
    )
    sip_password: str | None = Field(
        default=None,
        validation_alias="SIP_PASSWORD",
    )

    # Asterisk ARI + RTP (медиа к Pipecat по UDP, см. README фаза 11)
    asterisk_url: str | None = Field(
        default=None,
        validation_alias="ASTERISK_URL",
    )
    asterisk_ari_user: str | None = Field(
        default=None,
        validation_alias="ASTERISK_ARI_USER",
    )
    asterisk_ari_password: str | None = Field(
        default=None,
        validation_alias="ASTERISK_ARI_PASSWORD",
    )
    asterisk_stasis_app: str = Field(
        default="voice_ai_app",
        validation_alias="ASTERISK_STASIS_APP",
    )
    asterisk_rtp_advertise_host: str = Field(
        default="web",
        validation_alias="ASTERISK_RTP_ADVERTISE_HOST",
    )
    asterisk_rtp_port_min: int = Field(
        default=18000,
        ge=1024,
        le=65534,
        validation_alias="ASTERISK_RTP_PORT_MIN",
    )
    asterisk_rtp_port_max: int = Field(
        default=18015,
        ge=1024,
        le=65535,
        validation_alias="ASTERISK_RTP_PORT_MAX",
    )

    # Локальные WAV записи голосовых сессий (стерео: L — пользователь, R — бот). Пусто — не писать файлы.
    call_recordings_dir: str | None = Field(
        default="data/recordings",
        validation_alias="CALL_RECORDINGS_DIR",
    )

    @model_validator(mode="after")
    def _asterisk_rtp_port_order(self):
        if self.asterisk_rtp_port_max < self.asterisk_rtp_port_min:
            raise ValueError("ASTERISK_RTP_PORT_MAX должен быть >= ASTERISK_RTP_PORT_MIN")
        return self

    @field_validator("app_timezone", mode="before")
    @classmethod
    def _normalize_app_timezone(cls, value: object) -> str:
        """Пустая строка из .env — дефолт Europe/Saratov."""
        if value is None or value == "":
            return "Europe/Saratov"
        if not isinstance(value, str):
            return "Europe/Saratov"
        s = value.strip()
        return s or "Europe/Saratov"

    @field_validator("app_timezone", mode="after")
    @classmethod
    def _validate_app_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as e:
            msg = f"Неизвестный часовой пояс APP_TIMEZONE: {value}"
            raise ValueError(msg) from e
        return value

    @property
    def app_zoneinfo(self) -> ZoneInfo:
        """ZoneInfo для ``app_timezone`` (без кэша — строка уже провалидирована)."""
        return ZoneInfo(self.app_timezone)

    @field_validator("openai_api_key", mode="before")
    @classmethod
    def _normalize_openai_api_key(cls, value: object) -> object:
        """Пустая строка из .env трактуется как отсутствие ключа."""
        if value == "":
            return None
        return value

    @field_validator(
        "deepgram_api_key",
        "elevenlabs_api_key",
        "elevenlabs_voice_id",
        "bitrix24_webhook_url",
        "sip_server_ip",
        "sip_user",
        "sip_password",
        "asterisk_url",
        "asterisk_ari_user",
        "asterisk_ari_password",
        "salutespeech_auth_key",
        "deepseek_api_key",
        "telegram_bot_token",
        "max_bot_token",
        mode="before",
    )
    @classmethod
    def _normalize_optional_secrets(cls, value: object) -> object:
        """Пустые строки для опциональных секретов трактуются как None."""
        if value == "":
            return None
        return value

    @field_validator("voice_stt_provider", mode="before")
    @classmethod
    def _normalize_voice_stt_provider(cls, value: object) -> str:
        v = (value or "deepgram")
        if not isinstance(v, str):
            return "deepgram"
        v = v.strip().lower()
        if v not in ("deepgram", "salutespeech"):
            raise ValueError("VOICE_STT_PROVIDER должен быть 'deepgram' или 'salutespeech'")
        return v

    @field_validator("call_recordings_dir", mode="before")
    @classmethod
    def _normalize_call_recordings_dir(cls, value: object) -> object:
        if value is None or value == "":
            return None
        if isinstance(value, str):
            s = value.strip()
            return s or None
        return value

    @field_validator("voice_tts_provider", mode="before")
    @classmethod
    def _normalize_voice_tts_provider(cls, value: object) -> str:
        v = (value or "openai")
        if not isinstance(v, str):
            return "openai"
        v = v.strip().lower()
        if v not in ("openai", "elevenlabs", "salutespeech"):
            raise ValueError("VOICE_TTS_PROVIDER должен быть 'openai', 'elevenlabs' или 'salutespeech'")
        return v

    @property
    def environment(self) -> str:
        """Синоним для совместимости с терминологией README."""
        return self.app_env

    @property
    def debug(self) -> bool:
        """Синоним для флага отладки."""
        return self.app_debug


@lru_cache
def get_settings() -> Settings:
    """Возвращает закэшированный экземпляр настроек (удобно для DI в FastAPI)."""
    return Settings()


def llm_system_time_prefix() -> str:
    """Префикс в начале system prompt: локальные дата/время и часовой пояс приложения."""
    s = get_settings()
    tz = s.app_zoneinfo
    current_time = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S (%A)")
    return (
        f"Системная информация: Текущая дата и время {current_time}. "
        f"Часовой пояс: {s.app_timezone}. Учитывай это при ответах.\n\n"
    )
