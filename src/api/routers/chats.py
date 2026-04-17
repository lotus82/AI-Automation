"""REST API истории чатов для панели «Боты»."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from src.api.dependencies import ChatSessionQueryRepositoryDep
from src.api.dependencies_portal import PortalUserDep
from src.api.org_scope import resolve_organization_scope
from src.api.schemas.chats import (
    ChatHistoryResponse,
    ChatMessageItem,
    ChatSessionListItem,
    ChatSessionsListResponse,
)

router = APIRouter(tags=["chats"])


@router.get(
    "/chats",
    response_model=ChatSessionsListResponse,
    status_code=status.HTTP_200_OK,
    summary="Список сессий чатов с превью последнего сообщения",
)
async def list_chat_sessions(
    user: PortalUserDep,
    repo: ChatSessionQueryRepositoryDep,
    organization_id: UUID | None = Query(
        None,
        description="Супер-админ: область организации; без параметра — только legacy-диалоги без привязки к организации",
    ),
    limit: int = Query(default=200, ge=1, le=500),
) -> ChatSessionsListResponse:
    scope = resolve_organization_scope(user, organization_id)
    rows = await repo.list_session_summaries(organization_id=scope, limit=limit)
    items = [
        ChatSessionListItem(
            session_id=r.session_id,
            user_label=r.user_label,
            last_preview=r.last_preview,
            last_at=r.last_at,
        )
        for r in rows
    ]
    return ChatSessionsListResponse(items=items)


@router.get(
    "/chats/{session_id}",
    response_model=ChatHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Полная история сообщений сессии",
)
async def get_chat_history(
    user: PortalUserDep,
    session_id: str,
    repo: ChatSessionQueryRepositoryDep,
    organization_id: UUID | None = Query(
        None,
        description="Супер-админ: область организации; без параметра — только legacy-сообщения",
    ),
) -> ChatHistoryResponse:
    scope = resolve_organization_scope(user, organization_id)
    total_any_org = await repo.count_messages_in_session(session_id)
    messages = await repo.list_messages_chronological(session_id, organization_id=scope)
    if total_any_org > 0 and not messages:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сессия не найдена")
    return ChatHistoryResponse(
        session_id=session_id.strip(),
        messages=[
            ChatMessageItem(
                id=m.id,
                role=m.role,
                content=m.content,
                user_display=m.user_display,
                created_at=m.created_at,
            )
            for m in messages
            if m.id is not None
        ],
    )
