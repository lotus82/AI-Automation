"""Исходящие HTTP-вызовы к внешним системам через httpx."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import quote

import httpx

from src.application.interfaces.providers.api_provider import IExternalAPIProvider
from src.domain.entities.integration import (
    ApiKeyAuthConfig,
    BasicAuthConfig,
    BearerAuthConfig,
    Integration,
    IntegrationAction,
    NoAuthConfig,
)
from src.domain.exceptions.integration_exceptions import IntegrationCallError

_PATH_PLACEHOLDER = re.compile(r"\{([a-zA-Z0-9_]+)\}")


def _format_path(path: str, input_params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Подставляет ``{name}`` из ``input_params`` и возвращает остаток для query/body."""
    rest = dict(input_params)
    chunks: list[str] = []
    pos = 0
    for m in _PATH_PLACEHOLDER.finditer(path):
        chunks.append(path[pos : m.start()])
        key = m.group(1)
        if key not in rest:
            raise IntegrationCallError(f"Missing path parameter: {key}")
        raw = rest.pop(key)
        chunks.append(quote(str(raw), safe=""))
        pos = m.end()
    chunks.append(path[pos:])
    return "".join(chunks), rest


def _build_url(integration: Integration, path: str) -> str:
    base = str(integration.base_url).rstrip("/")
    rel = path if path.startswith("/") else f"/{path}"
    return f"{base}{rel}"


def _auth_headers_and_httpx_auth(
    integration: Integration,
) -> tuple[dict[str, str], httpx.Auth | None]:
    """Заголовки авторизации и опционально httpx Basic auth."""
    auth = integration.auth
    headers: dict[str, str] = {}

    if isinstance(auth, NoAuthConfig):
        return headers, None
    if isinstance(auth, BearerAuthConfig):
        headers["Authorization"] = f"Bearer {auth.token.get_secret_value()}"
        return headers, None
    if isinstance(auth, ApiKeyAuthConfig):
        headers[auth.header_name.strip()] = auth.header_value.get_secret_value()
        return headers, None
    if isinstance(auth, BasicAuthConfig):
        return headers, httpx.BasicAuth(
            auth.username,
            auth.password.get_secret_value(),
        )
    raise IntegrationCallError(f"Unsupported auth_type: {type(auth).__name__}")


def _response_json(response: httpx.Response) -> dict[str, Any]:
    if not response.content or not response.content.strip():
        return {}
    try:
        data = response.json()
    except json.JSONDecodeError as exc:
        raise IntegrationCallError(
            "Response body is not valid JSON",
            status_code=response.status_code,
            detail=(response.text or "")[:2000],
            url=str(response.url),
        ) from exc
    if isinstance(data, dict):
        return data
    return {"_data": data}


class HttpxAPIProvider(IExternalAPIProvider):
    """Реализация ``IExternalAPIProvider`` на ``httpx.AsyncClient``."""

    def __init__(self, *, timeout_sec: float = 30.0) -> None:
        self._timeout = timeout_sec

    async def execute(
        self,
        integration: Integration,
        action: IntegrationAction,
        input_params: dict[str, Any],
    ) -> dict[str, Any]:
        path_resolved, remainder = _format_path(action.path, dict(input_params))
        url = _build_url(integration, path_resolved)
        extra_headers, httpx_auth = _auth_headers_and_httpx_auth(integration)

        m = action.method.upper()
        params_kw: dict[str, Any] | None = None
        json_kw: Any | None = None
        if m in ("GET", "DELETE"):
            params_kw = remainder if remainder else None
        elif m in ("POST", "PUT", "PATCH"):
            json_kw = remainder if remainder else None
        else:
            raise IntegrationCallError(f"Unsupported HTTP method: {action.method}")

        timeout = httpx.Timeout(self._timeout)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.request(
                    m,
                    url,
                    headers=extra_headers or None,
                    auth=httpx_auth,
                    params=params_kw,
                    json=json_kw,
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            resp = exc.response
            text = (resp.text or "")[:2000]
            raise IntegrationCallError(
                f"HTTP error {resp.status_code}",
                status_code=resp.status_code,
                detail=text,
                url=str(resp.request.url),
            ) from exc
        except httpx.RequestError as exc:
            req_url = str(exc.request.url) if exc.request else None
            raise IntegrationCallError(f"HTTP request failed: {exc}", url=req_url) from exc

        return _response_json(response)
