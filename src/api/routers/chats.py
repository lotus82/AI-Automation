"""REST API истории чатов для панели «Боты»."""

from __future__ import annotations

from fastapi import APIRouter, Query, status

from src.api.dependencies import ChatSessionQueryRepositoryDep
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
    repo: ChatSessionQueryRepositoryDep,
    limit: int = Query(default=200, ge=1, le=500),
) -> ChatSessionsListResponse:
    rows = await repo.list_session_summaries(limit=limit)
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
    session_id: str,
    repo: ChatSessionQueryRepositoryDep,
) -> ChatHistoryResponse:
    messages = await repo.list_messages_chronological(session_id)
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
