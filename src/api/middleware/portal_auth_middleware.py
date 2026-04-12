"""Проверка JWT для HTTP-запросов к API панели (кроме публичных путей)."""

from __future__ import annotations

import re
from typing import Callable

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.core.config import get_settings
from src.infrastructure.portal_security import decode_portal_token

_UUID_RE = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"

# Публичное прохождение опроса
_RE_QUESTIONNAIRE_GET = re.compile(rf"^/api/questionnaires/{_UUID_RE}$")
_RE_QUESTIONNAIRE_ASSESS = re.compile(rf"^/api/questionnaires/{_UUID_RE}/assess$")


def _is_public_path(path: str, method: str) -> bool:
    if method == "OPTIONS":
        return True
    if path == "/api/health" and method == "GET":
        return True
    if path == "/api/auth/login" and method == "POST":
        return True
    if path.startswith("/docs") or path.startswith("/redoc") or path == "/openapi.json":
        return True
    if path.startswith("/api/max/"):
        return True
    if path.startswith("/api/bitrix/"):
        return True
    if path.startswith("/voice/"):
        return True
    if path == "/api/chat/text" and method == "POST":
        return True
    if path == "/api/chat/finalize" and method == "POST":
        return True
    if path == "/api/leads" and method == "POST":
        return True
    if method == "GET" and _RE_QUESTIONNAIRE_GET.match(path):
        return True
    if method == "POST" and _RE_QUESTIONNAIRE_ASSESS.match(path):
        return True
    return False


class PortalAuthMiddleware(BaseHTTPMiddleware):
    """Требует заголовок Authorization: Bearer … для защищённых маршрутов."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Response]) -> Response:
        path = request.url.path
        method = request.method.upper()
        if _is_public_path(path, method):
            return await call_next(request)

        auth = request.headers.get("Authorization")
        if not auth or not auth.startswith("Bearer "):
            return JSONResponse({"detail": "Требуется авторизация"}, status_code=401)
        token = auth[7:].strip()
        if not token:
            return JSONResponse({"detail": "Требуется авторизация"}, status_code=401)
        settings = get_settings()
        try:
            payload = decode_portal_token(token, settings.portal_jwt_secret)
        except Exception:
            return JSONResponse({"detail": "Недействительный или просроченный токен"}, status_code=401)
        if payload.get("typ") != "portal" or not payload.get("sub"):
            return JSONResponse({"detail": "Недействительный токен"}, status_code=401)
        request.state.portal_token_payload = payload
        return await call_next(request)
