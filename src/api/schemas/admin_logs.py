"""Схемы API просмотра логов Docker (панель отладки)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ContainerLogItem(BaseModel):
    id: str = Field(description="Полный ID контейнера")
    short_id: str
    names: list[str] = Field(default_factory=list)
    image: str = ""
    state: str = ""
    status: str = ""


class ContainerLogsResponse(BaseModel):
    text: str = Field(default="", description="Текст логов (stdout+stderr)")


class ContainersListResponse(BaseModel):
    containers: list[ContainerLogItem]
