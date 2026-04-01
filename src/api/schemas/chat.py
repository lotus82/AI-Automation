"""Схемы HTTP для текстового чата (RAG)."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class ChatTextRequest(BaseModel):
    """Текстовое сообщение пользователя и опциональный идентификатор сессии."""

    message: str = Field(..., min_length=1, max_length=8000)
    session_id: UUID | None = Field(
        default=None,
        description="Если не передан, создаётся новая сессия диалога",
    )


class ChatTextResponse(BaseModel):
    """Ответ ассистента и идентификатор сессии (для продолжения диалога)."""

    reply: str = Field(..., description="Сгенерированный текст ответа")
    session_id: UUID = Field(..., description="Идентификатор сессии в Redis")


class ChatFinalizeRequest(BaseModel):
    """Явное завершение текстовой сессии — постановка задачи ОКК в Celery."""

    session_id: UUID = Field(..., description="Идентификатор сессии в Redis")


class ChatFinalizeResponse(BaseModel):
    """Подтверждение постановки анализа в очередь."""

    status: str = Field(default="queued", description="Статус постановки задачи")
    session_id: UUID = Field(..., description="Идентификатор сессии")
