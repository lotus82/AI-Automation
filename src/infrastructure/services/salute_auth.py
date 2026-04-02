"""OAuth2 SaluteSpeech: обмен Authorization Key на access_token с кэшем в Redis."""

from __future__ import annotations

import asyncio
import base64
import json
import uuid
from typing import Final

import httpx
from loguru import logger
from redis.asyncio import Redis

# TTL кэша короче 30 минут срока жизни токена (требование фазы 13).
_DEFAULT_CACHE_TTL_SEC: Final[int] = 25 * 60
_OAUTH_URL: Final[str] = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
_REDIS_KEY: Final[str] = "salutespeech:oauth:access_token:v1"


def _redis_get_as_str(value: str | bytes | None) -> str | None:
    """Унификация ответа Redis: при ``decode_responses=True`` уже ``str``, иначе часто ``bytes``."""
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


def normalize_salutespeech_basic_credentials(raw: str) -> str:
    """Готовит значение для заголовка Authorization: Basic …

    - Если строка вида ``client_id:client_secret`` — кодируем в Base64 (UTF-8).
    - Иначе считаем, что это уже **Authorization Key** из Studio (как в официальных примерах).
    """
    s = raw.strip()
    if not s:
        return s
    if ":" in s:
        return base64.b64encode(s.encode("utf-8")).decode("ascii")
    return s


_OAUTH_RETRYABLE: Final[tuple[type[BaseException], ...]] = (
    httpx.ConnectError,
    httpx.TimeoutException,
    httpx.ReadError,
    httpx.RemoteProtocolError,
)


class SaluteSpeechAuthManager:
    """Асинхронное получение access_token с кэшем в Redis (TTL 25 минут)."""

    def __init__(
        self,
        redis: Redis,
        *,
        authorization_key: str,
        scope: str = "SALUTE_SPEECH_PERS",
        oauth_url: str | None = None,
        oauth_verify_ssl: bool = False,
        oauth_retries: int = 3,
        oauth_trust_env: bool = False,
        cache_ttl_seconds: int = _DEFAULT_CACHE_TTL_SEC,
        redis_key: str = _REDIS_KEY,
    ) -> None:
        self._redis = redis
        self._basic_secret = normalize_salutespeech_basic_credentials(authorization_key)
        self._scope = scope.strip() or "SALUTE_SPEECH_PERS"
        self._oauth_url = (oauth_url or _OAUTH_URL).strip() or _OAUTH_URL
        self._oauth_verify = oauth_verify_ssl
        self._oauth_retries = max(1, oauth_retries)
        self._oauth_trust_env = oauth_trust_env
        self._oauth_timeout = httpx.Timeout(60.0, connect=25.0)
        self._ttl = cache_ttl_seconds
        self._redis_key = redis_key

    @property
    def scope(self) -> str:
        return self._scope

    async def prewarm(self) -> None:
        """Прогрев токена до старта пайплайна (рекомендуется вызывать из оркестратора)."""
        await self.get_access_token()

    async def get_access_token(self) -> str:
        if not self._basic_secret:
            msg = "SaluteSpeech: пустой ключ авторизации (SALUTESPEECH_AUTH_KEY / system_settings)"
            raise ValueError(msg)

        cached = await self._redis.get(self._redis_key)
        text = _redis_get_as_str(cached)
        if text:
            return text

        token = await self._fetch_token_from_oauth()
        await self._redis.set(self._redis_key, token, ex=self._ttl)
        return token

    async def invalidate_cache(self) -> None:
        """Сброс кэша (например после 401 от SmartSpeech)."""
        await self._redis.delete(self._redis_key)

    async def _fetch_token_from_oauth(self) -> str:
        rq_uid = str(uuid.uuid4())
        headers = {
            "Authorization": f"Basic {self._basic_secret}",
            "RqUID": rq_uid,
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        # Как в официальных примерах SaluteSpeech: только scope (без grant_type).
        data = {"scope": self._scope}

        last_exc: BaseException | None = None
        resp: httpx.Response | None = None
        for attempt in range(1, self._oauth_retries + 1):
            try:
                async with httpx.AsyncClient(
                    verify=self._oauth_verify,
                    timeout=self._oauth_timeout,
                    trust_env=self._oauth_trust_env,
                    http2=False,
                ) as client:
                    resp = await client.post(self._oauth_url, headers=headers, data=data)
                break
            except _OAUTH_RETRYABLE as e:
                last_exc = e
                if attempt >= self._oauth_retries:
                    logger.error(
                        "SaluteSpeech OAuth: сеть к %s после %s попыток: %s. "
                        "Проверьте исходящий TCP/HTTPS к хосту шлюза (порт 9443), VPN в РФ, файрвол и "
                        "переменные HTTP_PROXY/HTTPS_PROXY; при необходимости SALUTESPEECH_OAUTH_TRUST_ENV=true "
                        "или SALUTESPEECH_OAUTH_URL (прокси/другой endpoint).",
                        self._oauth_url,
                        self._oauth_retries,
                        e,
                    )
                    raise
                wait = 1.5 * attempt
                logger.warning(
                    "SaluteSpeech OAuth: попытка %s/%s не удалась (%s), пауза %.1f с",
                    attempt,
                    self._oauth_retries,
                    type(e).__name__,
                    wait,
                )
                await asyncio.sleep(wait)

        if resp is None:
            msg = "SaluteSpeech OAuth: нет ответа"
            raise RuntimeError(msg) from last_exc

        if resp.status_code != 200:
            logger.warning(
                "SaluteSpeech OAuth HTTP %s: %s",
                resp.status_code,
                resp.text[:500],
            )
            resp.raise_for_status()

        try:
            payload = resp.json()
            token = payload["access_token"]
        except (KeyError, json.JSONDecodeError) as e:
            msg = f"SaluteSpeech OAuth: неожиданный ответ: {resp.text[:300]}"
            raise ValueError(msg) from e

        return str(token)
