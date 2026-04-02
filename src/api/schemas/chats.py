"""Схемы API списка чатов и истории (мониторинг ботов)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ChatSessionListItem(BaseModel):
    """Одна строка таблицы активных сессий."""

    session_id: str
    user_label: str | None = None
    last_preview: str
    last_at: datetime | None = None


class ChatSessionsListResponse(BaseModel):
    """Ответ GET /api/chats."""

    items: list[ChatSessionListItem]


class ChatMessageItem(BaseModel):
    """Сообщение в хронологии."""

    id: UUID
    role: str
    content: str
    user_display: str | None = None
    created_at: datetime | None = None


class ChatHistoryResponse(BaseModel):
    """Ответ GET /api/chats/{session_id}."""

    session_id: str
    messages: list[ChatMessageItem] = Field(default_factory=list)
