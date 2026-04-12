"""Bitrix24 Marketplace Server App: установка, события, UI iframe."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from pydantic import ValidationError
from starlette.datastructures import UploadFile

from src.api.dependencies import AsyncSessionDep, BitrixPortalRepoDep, SettingsDep
from src.api.schemas.bitrix import (
    BitrixInstallPayload,
    BitrixWebhookPayload,
    bitrix_install_from_flat_mapping,
    normalize_bitrix_portal_url,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bitrix", tags=["bitrix24"])


def _merge_bitrix_install_query_into_raw(request: Request, raw: dict[str, Any]) -> dict[str, Any]:
    """Битрикс24 POST на /install часто с query (?DOMAIN=…&APP_SID=…), OAuth — в теле; без merge нет auth.domain."""
    qflat = {
        str(k): str(v).strip()
        for k, v in request.query_params.multi_items()
        if v is not None and str(v).strip() != ""
    }
    if not qflat:
        return raw
    auth = raw.get("auth")
    if isinstance(auth, dict):
        for qkey, field in (
            ("DOMAIN", "domain"),
            ("domain", "domain"),
            ("MEMBER_ID", "member_id"),
            ("member_id", "member_id"),
        ):
            val = qflat.get(qkey)
            if val and not (auth.get(field) and str(auth.get(field)).strip()):
                auth[field] = val
        return raw
    # Тело плоское: query не перетирает ключи из тела
    return {**qflat, **raw}


async def _read_install_payload(request: Request) -> BitrixInstallPayload:
    """Читает JSON или ``application/x-www-form-urlencoded`` (типичный POST установки из Битрикс24)."""
    ct = (request.headers.get("content-type") or "").lower()
    raw: dict[str, Any]
    try:
        if "application/json" in ct:
            body = await request.json()
            if not isinstance(body, dict):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="JSON установки должен быть объектом",
                )
            raw = body
        else:
            form = await request.form()
            raw = {}
            for k, v in form.multi_items():
                if isinstance(v, UploadFile):
                    continue
                raw[str(k)] = str(v)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Bitrix install: ошибка чтения тела: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не удалось прочитать тело запроса установки",
        ) from exc
    raw = _merge_bitrix_install_query_into_raw(request, raw)
    try:
        return bitrix_install_from_flat_mapping(raw)
    except (ValidationError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Невалидные данные установки: {exc}",
        ) from exc


async def _read_webhook_payload(request: Request) -> BitrixWebhookPayload:
    ct = (request.headers.get("content-type") or "").lower()
    try:
        if "application/json" in ct:
            body = await request.json()
            if not isinstance(body, dict):
                raise ValueError("ожидался объект")
            return BitrixWebhookPayload.model_validate(body)
        form = await request.form()
        raw = {str(k): str(v) for k, v in form.multi_items() if not isinstance(v, UploadFile)}
        return BitrixWebhookPayload.model_validate(raw)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Невалидное событие Bitrix24: {exc}",
        ) from exc


@router.post(
    "/install",
    response_class=HTMLResponse,
    summary="Первичная установка приложения (OAuth)",
)
async def bitrix_install(
    request: Request,
    session: AsyncSessionDep,
    repo: BitrixPortalRepoDep,
    settings: SettingsDep,
) -> HTMLResponse:
    """Сохраняет токены портала; ответ — HTML для отображения внутри iframe установки Битрикс24."""
    payload = await _read_install_payload(request)
    auth = payload.auth
    portal_url = auth.portal_url
    if not portal_url:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Пустой domain портала")

    expires_at: datetime | None = None
    if auth.expires is not None:
        try:
            expires_at = datetime.fromtimestamp(int(auth.expires), tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            expires_at = None
    if expires_at is None and auth.expires_in is not None:
        try:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(auth.expires_in))
        except (TypeError, ValueError):
            expires_at = None

    await repo.upsert_install(
        portal_url=portal_url,
        member_id=auth.member_id.strip(),
        access_token=auth.access_token.strip(),
        refresh_token=auth.refresh_token.strip(),
        expires_at=expires_at,
    )
    logger.info("Bitrix24 install: портал %s member_id=%s", portal_url, auth.member_id)
    # Сессия фиксируется зависимостью get_async_session после успешного ответа
    hint = ""
    if not (settings.bitrix24_oauth_client_id and settings.bitrix24_oauth_client_secret):
        hint = "<p><strong>Внимание:</strong> задайте BITRIX24_OAUTH_CLIENT_ID и BITRIX24_OAUTH_CLIENT_SECRET для refresh токенов.</p>"
    html = f"""<!DOCTYPE html>
<html lang="ru">
<head><meta charset="utf-8"><title>Установка</title></head>
<body>
  <p>Приложение успешно установлено на портал <code>{portal_url}</code>.</p>
  {hint}
</body>
</html>"""
    return HTMLResponse(content=html, status_code=status.HTTP_200_OK)


@router.post(
    "/events",
    summary="Входящие события приложения (ONCRMLEADADD и др.)",
)
async def bitrix_events(
    request: Request,
    session: AsyncSessionDep,
    repo: BitrixPortalRepoDep,
    settings: SettingsDep,
) -> dict[str, str]:
    """Проверяет ``application_token`` и домен, ставит обработку в Celery."""
    body = await _read_webhook_payload(request)

    expected = (settings.bitrix24_application_token or "").strip()
    if expected:
        got = (body.auth.application_token or "").strip()
        if got != expected:
            logger.warning("Bitrix24 events: неверный application_token для domain=%s", body.auth.domain)
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Неверный application_token")

    portal_url = normalize_bitrix_portal_url(body.auth.domain)
    portal = await repo.get_by_portal_url(portal_url)
    if portal is None or not portal.is_active:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Портал не найден или отключён; выполните установку приложения",
        )

    from src.workers.tasks import process_bitrix24_event_task

    process_bitrix24_event_task.delay(str(portal.id), body.event, body.data)
    return {"status": "ok"}


@router.post(
    "/index",
    response_class=HTMLResponse,
    summary="Пользовательский интерфейс (iframe)",
)
async def bitrix_index(
    request: Request,
) -> HTMLResponse:
    """Минимальная страница для встраивания в Битрикс24 (PLACEMENT_DEFAULT и т.п.)."""
    _ = request  # при необходимости разбора PLACEMENT / DOMAIN из form
    html = """<!DOCTYPE html>
<html lang="ru">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>ИИ-агент</title></head>
<body>
  <h1>Приложение</h1>
  <p>Серверное приложение активно. Настройте обработку событий в фоновых задачах.</p>
</body>
</html>"""
    return HTMLResponse(content=html, status_code=status.HTTP_200_OK)
