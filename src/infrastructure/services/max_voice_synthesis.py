"""Фабрика синтеза речи для MAX: SaluteSpeech REST → Opus OGG (фаза 22); Pipecat остаётся на gRPC."""

from __future__ import annotations

import logging

from redis.asyncio import Redis

from src.core.config import Settings
from src.domain import system_setting_keys as sk
from src.infrastructure.services.salute_auth import SaluteSpeechAuthManager
from src.infrastructure.voice.salute_tts import SaluteSpeechTTSService
from src.use_cases.interfaces import IMaxVoiceSynthesizer, ISettingsRepository

logger = logging.getLogger(__name__)


class SaluteSpeechMaxVoiceSynthesizer(IMaxVoiceSynthesizer):
    """Обёртка над **SaluteSpeechTTSService** для MAX (один вызов → байты Opus в OGG)."""

    def __init__(self, tts: SaluteSpeechTTSService) -> None:
        self._tts = tts

    async def synthesize_to_file(self, text: str) -> bytes:
        return await self._tts.synthesize_to_file(text)


async def create_salute_max_voice_synthesizer(
    settings_repo: ISettingsRepository,
    redis: Redis,
    app_settings: Settings,
) -> IMaxVoiceSynthesizer | None:
    """Собирает синтезатор, если в БД или env задан ключ SaluteSpeech; иначе ``None``."""
    auth_key = (await settings_repo.get_value(sk.SALUTESPEECH_AUTH_KEY) or "").strip()
    if not auth_key and app_settings.salutespeech_auth_key:
        auth_key = (app_settings.salutespeech_auth_key or "").strip()
    if not auth_key:
        logger.debug("MAX озвучка: нет SALUTESPEECH_AUTH_KEY — синтез отключён")
        return None

    scope = (
        (await settings_repo.get_value(sk.SALUTESPEECH_SCOPE) or "").strip()
        or app_settings.salutespeech_scope
    )
    voice = (
        (await settings_repo.get_value(sk.SALUTESPEECH_VOICE) or "").strip()
        or app_settings.salutespeech_voice
    )

    auth = SaluteSpeechAuthManager(
        redis,
        authorization_key=auth_key,
        scope=scope,
        oauth_url=app_settings.salutespeech_oauth_url,
        oauth_verify_ssl=app_settings.salutespeech_oauth_verify_ssl,
        oauth_retries=app_settings.salutespeech_oauth_retries,
        oauth_trust_env=app_settings.salutespeech_oauth_trust_env,
    )
    tts = SaluteSpeechTTSService(
        auth_manager=auth,
        grpc_target=app_settings.salutespeech_grpc_target,
        voice=voice,
        smartspeech_verify_ssl=app_settings.salutespeech_smartspeech_verify_ssl,
        rest_base_url=app_settings.salutespeech_rest_base_url,
    )
    return SaluteSpeechMaxVoiceSynthesizer(tts)
