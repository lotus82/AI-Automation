"""WebSocket-уведомления для панели мониторинга диалогов."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from src.core.config import get_settings
from src.infrastructure.monitoring import get_chat_events_broadcaster
from src.infrastructure.portal_security import decode_portal_token

router = APIRouter(tags=["notifications"])


def _parse_uuid_query(raw: str | None) -> UUID | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    return UUID(s)


@router.websocket("/ws/monitoring")
async def monitoring_websocket(
    websocket: WebSocket,
    token: str | None = Query(default=None, description="JWT портала (тот же, что в Authorization для REST)"),
    organization_id: str | None = Query(
        default=None,
        description="Область событий: у пользователя организации совпадает с JWT; супер-админ — выбор организации",
    ),
) -> None:
    """Подписка на события ``new_message`` (рассылает ``ChatEventsBroadcaster``) с изоляцией по организации."""
    await websocket.accept()
    if not token or not token.strip():
        await websocket.close(code=1008, reason="Unauthorized")
        return
    try:
        payload = decode_portal_token(token.strip(), get_settings().portal_jwt_secret)
        if payload.get("typ") != "portal" or not payload.get("sub"):
            raise ValueError("bad token")
    except Exception:
        await websocket.close(code=1008, reason="Unauthorized")
        return

    raw_org = payload.get("org_id")
    token_org: UUID | None = None
    if raw_org is not None and str(raw_org).strip():
        try:
            token_org = UUID(str(raw_org).strip())
        except ValueError:
            await websocket.close(code=1008, reason="Unauthorized")
            return

    try:
        query_org = _parse_uuid_query(organization_id)
    except ValueError:
        await websocket.close(code=1008, reason="Bad organization_id")
        return

    if token_org is not None:
        if query_org is not None and query_org != token_org:
            await websocket.close(code=1008, reason="Forbidden")
            return
        listener_scope = token_org
    else:
        listener_scope = query_org

    broadcaster = get_chat_events_broadcaster()
    await broadcaster.adopt(websocket, listener_scope=listener_scope)
    try:
        while True:
            # Держим соединение; клиент может слать ping-текст.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await broadcaster.unregister(websocket)
