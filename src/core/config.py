"""Управление конфигурацией через Pydantic Settings."""

from datetime import datetime
from functools import lru_cache
from uuid import UUID
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
    # Fernet (URL-safe base64, 44 символа): шифрование секретов интеграций в JSONB (см. cryptography.fernet.Fernet.generate_key)
    integration_fernet_key: str | None = Field(
        default=None,
        validation_alias="INTEGRATION_FERNET_KEY",
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
    openai_agent_model: str = Field(
        default="gpt-4o-mini",
        validation_alias="OPENAI_AGENT_MODEL",
        description="Модель Chat Completions для агента с инструментами (интеграции).",
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
    # Токен сообщества VK API (messages) для уведомлений продавца из витрины магазина
    vk_api_access_token: str | None = Field(
        default=None,
        validation_alias="VK_API_ACCESS_TOKEN",
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
    # Опционально: при отладке — только один контекст long poll (иначе по одному воркеру на уникальный MAX_BOT_TOKEN)
    max_long_poll_organization_id: UUID | None = Field(
        default=None,
        validation_alias="MAX_LONG_POLL_ORGANIZATION_ID",
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
    # Marketplace Server App (OAuth): клиент и секрет с портала разработчика; application_token — секрет проверки вебхуков
    bitrix24_oauth_client_id: str | None = Field(
        default=None,
        validation_alias="BITRIX24_OAUTH_CLIENT_ID",
    )
    bitrix24_oauth_client_secret: str | None = Field(
        default=None,
        validation_alias="BITRIX24_OAUTH_CLIENT_SECRET",
    )
    bitrix24_application_token: str | None = Field(
        default=None,
        validation_alias="BITRIX24_APPLICATION_TOKEN",
        description="Секрет приложения для валидации auth[application_token] во входящих событиях.",
    )
    # Публичный origin SPA (схема+хост[:порт]) для ссылок в iframe после install; иначе берётся из Host и часто получается http за прокси → Mixed Content в Битрикс24
    bitrix24_public_app_origin: str | None = Field(
        default=None,
        validation_alias="BITRIX24_PUBLIC_APP_ORIGIN",
        description="Например https://lotus-it.ru — редирект после POST /api/bitrix/install.",
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
    # Витрины магазинов: логотипы и фото товаров на диске
    shop_upload_dir: str = Field(
        default="data/shop_uploads",
        validation_alias="SHOP_UPLOAD_DIR",
    )

    # Портал: JWT для панели (обязательно задать в production)
    portal_jwt_secret: str = Field(
        default="dev-portal-jwt-secret-change-me",
        validation_alias="PORTAL_JWT_SECRET",
    )
    portal_jwt_expire_minutes: int = Field(
        default=1440,
        ge=15,
        le=10080,
        validation_alias="PORTAL_JWT_EXPIRE_MINUTES",
        description="Срок жизни access-токена портала (минуты), по умолчанию 24 ч.",
    )
    # МИС: JWT пациента после авторизации в Mini App MAX (тот же PORTAL_JWT_SECRET)
    mis_patient_jwt_expire_minutes: int = Field(
        default=10080,
        ge=60,
        le=525600,
        validation_alias="MIS_PATIENT_JWT_EXPIRE_MINUTES",
        description="Срок жизни токена пациента (мессенджер MAX), минуты; по умолчанию 7 суток.",
    )
    mis_max_init_data_max_age_sec: int = Field(
        default=3600,
        ge=60,
        le=86400,
        validation_alias="MIS_MAX_INIT_DATA_MAX_AGE_SEC",
        description="Допустимый возраст auth_date в initData MAX (секунды), см. dev.max.ru/docs/webapps/validation.",
    )
    mis_max_patient_mini_app_base_url: str | None = Field(
        default=None,
        validation_alias="MIS_MAX_PATIENT_MINI_APP_BASE_URL",
        description="Базовый URL мини-приложения пациента для deep link из бота (опционально).",
    )
    mis_patient_public_base_url: str | None = Field(
        default=None,
        validation_alias="MIS_PATIENT_PUBLIC_BASE_URL",
        description="Публичный origin SPA (https://домен) для ссылок на портал /public/mis/patient/… из бота MAX.",
    )

    # Панель «Логи»: Docker Engine API по Unix-сокету (монтирование в compose, токен в заголовке)
    admin_logs_token: str | None = Field(
        default=None,
        validation_alias="ADMIN_LOGS_TOKEN",
    )
    docker_socket_path: str = Field(
        default="/var/run/docker.sock",
        validation_alias="DOCKER_SOCKET_PATH",
    )
    docker_api_version: str = Field(
        default="1.41",
        validation_alias="DOCKER_API_VERSION",
    )

    @model_validator(mode="after")
    def _asterisk_rtp_port_order(self):
        if self.asterisk_rtp_port_max < self.asterisk_rtp_port_min:
            raise ValueError("ASTERISK_RTP_PORT_MAX должен быть >= ASTERISK_RTP_PORT_MIN")
        return self

    @model_validator(mode="after")
    def _portal_jwt_secret_in_production(self):
        if (self.app_env or "").lower() in ("production", "prod") and (
            not self.portal_jwt_secret
            or self.portal_jwt_secret.strip() == ""
            or self.portal_jwt_secret == "dev-portal-jwt-secret-change-me"
        ):
            raise ValueError("В production задайте безопасный PORTAL_JWT_SECRET в окружении")
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
        "bitrix24_oauth_client_id",
        "bitrix24_oauth_client_secret",
        "bitrix24_application_token",
        "bitrix24_public_app_origin",
        "sip_server_ip",
        "sip_user",
        "sip_password",
        "asterisk_url",
        "asterisk_ari_user",
        "asterisk_ari_password",
        "salutespeech_auth_key",
        "deepseek_api_key",
        "telegram_bot_token",
        "vk_api_access_token",
        "max_bot_token",
        "admin_logs_token",
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


_LLM_WEEKDAYS_RU = (
    "понедельник",
    "вторник",
    "среда",
    "четверг",
    "пятница",
    "суббота",
    "воскресенье",
)


def resolve_llm_clock_timezone(client_timezone_id: str | None) -> tuple[ZoneInfo, str]:
    """Часовой пояс для контекста LLM: IANA из клиента (заголовок), иначе пояс приложения."""
    s = get_settings()
    if client_timezone_id:
        raw = str(client_timezone_id).strip()
        if raw:
            try:
                return ZoneInfo(raw), raw
            except ZoneInfoNotFoundError:
                pass
    return s.app_zoneinfo, s.app_timezone


def llm_system_time_prefix(client_timezone_id: str | None = None) -> str:
    """Префикс system prompt: дата, время и день недели в выбранном поясе (клиента или приложения).

    Формат в тексте для модели: ДД.ММ.ГГГГ ЧЧ:ММ:СС (русское название дня недели).
    """
    tz, tz_name = resolve_llm_clock_timezone(client_timezone_id)
    now = datetime.now(tz)
    wd = _LLM_WEEKDAYS_RU[now.weekday()]
    dt_str = now.strftime("%d.%m.%Y %H:%M:%S")
    return (
        f"Системная информация: текущие дата и время в часовом поясе клиента ({tz_name}): "
        f"{dt_str}, день недели: {wd}. Учитывай это при ответах. "
        "В ответах пользователю выводи дату и время только в формате ДД.ММ.ГГГГ ЧЧ:ММ:СС.\n\n"
    )
