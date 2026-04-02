"""Схемы API базы знаний."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class KnowledgeItemResponse(BaseModel):
    id: UUID
    title: str
    content_preview: str = Field(description="Короткий фрагмент текста для списка")
    has_embedding: bool
    created_at: datetime | None = None


class KnowledgeUploadCreatedItem(BaseModel):
    id: UUID
    title: str


class KnowledgeUploadResponse(BaseModel):
    created_count: int
    items: list[KnowledgeUploadCreatedItem]
