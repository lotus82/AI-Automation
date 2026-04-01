"""Управление конфигурацией через Pydantic Settings."""

from functools import lru_cache

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
    # Провайдер синтеза: openai | elevenlabs (HTTP streaming, без локального TTS)
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

    @model_validator(mode="after")
    def _asterisk_rtp_port_order(self):
        if self.asterisk_rtp_port_max < self.asterisk_rtp_port_min:
            raise ValueError("ASTERISK_RTP_PORT_MAX должен быть >= ASTERISK_RTP_PORT_MIN")
        return self

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
        mode="before",
    )
    @classmethod
    def _normalize_optional_secrets(cls, value: object) -> object:
        """Пустые строки для опциональных секретов трактуются как None."""
        if value == "":
            return None
        return value

    @field_validator("voice_tts_provider", mode="before")
    @classmethod
    def _normalize_voice_tts_provider(cls, value: object) -> str:
        v = (value or "openai")
        if not isinstance(v, str):
            return "openai"
        v = v.strip().lower()
        if v not in ("openai", "elevenlabs"):
            raise ValueError("VOICE_TTS_PROVIDER должен быть 'openai' или 'elevenlabs'")
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
