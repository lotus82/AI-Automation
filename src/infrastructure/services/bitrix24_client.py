"""Асинхронный клиент REST Bitrix24 с OAuth refresh (Marketplace Server App)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import httpx

from src.infrastructure.models import BitrixPortalModel
from src.infrastructure.repositories import SqlAlchemyBitrixPortalRepository

logger = logging.getLogger(__name__)

BITRIX_OAUTH_TOKEN_URL = "https://oauth.bitrix.info/oauth/token/"
# Обновляем токен заранее, чтобы не ловить 401 на границе TTL
_REFRESH_SKEW = timedelta(seconds=90)


class Bitrix24Client:
    """Вызовы ``https://{{portal}}/rest/{{method}}.json`` с Bearer-параметром ``auth`` и refresh по OAuth."""

    def __init__(
        self,
        *,
        portal_url: str,
        access_token: str,
        refresh_token: str,
        expires_at: datetime | None,
        oauth_client_id: str,
        oauth_client_secret: str,
        portal_id: UUID,
        repo: SqlAlchemyBitrixPortalRepository,
        http_timeout_sec: float = 60.0,
    ) -> None:
        self._portal_url = portal_url.rstrip("/")
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._expires_at = expires_at
        self._client_id = oauth_client_id
        self._client_secret = oauth_client_secret
        self._portal_id = portal_id
        self._repo = repo
        self._http_timeout = http_timeout_sec

    @property
    def portal_url(self) -> str:
        return self._portal_url

    def _rest_method_url(self, method: str) -> str:
        m = (method or "").strip()
        if not m:
            raise ValueError("method пустой")
        return f"{self._portal_url}/rest/{m}.json"

    def _should_refresh(self) -> bool:
        now = datetime.now(timezone.utc)
        if self._expires_at is None:
            return True
        exp = self._expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        return exp <= now + _REFRESH_SKEW

    async def _refresh_tokens_if_needed(self) -> None:
        if not self._should_refresh():
            return
        if not self._client_id or not self._client_secret:
            logger.warning("Bitrix24Client: пропуск refresh — не заданы BITRIX24_OAUTH_CLIENT_ID/SECRET")
            return
        data = {
            "grant_type": "refresh_token",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "refresh_token": self._refresh_token,
        }
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(45.0, connect=15.0)) as client:
                resp = await client.post(BITRIX_OAUTH_TOKEN_URL, data=data)
        except httpx.HTTPError as exc:
            logger.exception("Bitrix24 OAuth refresh: сеть %s", exc)
            raise
        if resp.status_code >= 400:
            logger.error(
                "Bitrix24 OAuth refresh HTTP %s: %s",
                resp.status_code,
                (resp.text or "")[:800],
            )
            resp.raise_for_status()
        try:
            payload = resp.json()
        except ValueError as exc:
            msg = "Bitrix24 OAuth refresh: не JSON"
            raise RuntimeError(msg) from exc

        new_access = payload.get("access_token")
        new_refresh = payload.get("refresh_token") or self._refresh_token
        if not isinstance(new_access, str) or not new_access:
            msg = "Bitrix24 OAuth refresh: нет access_token в ответе"
            raise RuntimeError(msg)

        expires_at: datetime | None = None
        if payload.get("expires") is not None:
            try:
                expires_at = datetime.fromtimestamp(int(payload["expires"]), tz=timezone.utc)
            except (TypeError, ValueError, OSError):
                expires_at = None
        if expires_at is None and payload.get("expires_in") is not None:
            try:
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(payload["expires_in"]))
            except (TypeError, ValueError):
                expires_at = None

        self._access_token = new_access
        self._refresh_token = str(new_refresh)
        self._expires_at = expires_at

        await self._repo.update_tokens(
            self._portal_id,
            access_token=self._access_token,
            refresh_token=self._refresh_token,
            expires_at=self._expires_at,
        )
        logger.info("Bitrix24Client: токены обновлены для portal_id=%s", self._portal_id)

    async def call_api(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Универсальный вызов REST (например ``crm.deal.add``). Тело — JSON; ``auth`` передаётся query-параметром."""
        await self._refresh_tokens_if_needed()
        url = self._rest_method_url(method)
        body = params if params is not None else {}
        async with httpx.AsyncClient(timeout=self._http_timeout) as client:
            resp = await client.post(
                url,
                params={"auth": self._access_token},
                json=body,
            )
        if resp.status_code >= 400:
            logger.error(
                "Bitrix24 REST %s HTTP %s: %s",
                method,
                resp.status_code,
                (resp.text or "")[:800],
            )
            resp.raise_for_status()
        try:
            data = resp.json()
        except ValueError as exc:
            msg = f"Bitrix24 REST {method}: ответ не JSON"
            raise RuntimeError(msg) from exc
        if isinstance(data, dict) and data.get("error"):
            err = data.get("error")
            desc = data.get("error_description", "")
            msg = f"Bitrix24 REST error: {err} {desc}"
            raise RuntimeError(msg)
        return data if isinstance(data, dict) else {"result": data}


def bitrix24_client_from_portal(
    portal: BitrixPortalModel,
    repo: SqlAlchemyBitrixPortalRepository,
    *,
    oauth_client_id: str | None,
    oauth_client_secret: str | None,
) -> Bitrix24Client:
    """Фабрика клиента по строке БД и той же сессии, что у ``repo`` (удобно для DI в эндпоинтах)."""
    return Bitrix24Client(
        portal_url=portal.portal_url,
        access_token=portal.access_token,
        refresh_token=portal.refresh_token,
        expires_at=portal.expires_at,
        oauth_client_id=(oauth_client_id or "").strip(),
        oauth_client_secret=(oauth_client_secret or "").strip(),
        portal_id=portal.id,
        repo=repo,
    )
