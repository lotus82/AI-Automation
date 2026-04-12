"""Схемы API портала: вход, пользователи, организации."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from src.domain.portal_roles import ALL_SECTION_KEYS


class PortalLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


class PortalLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int


class PortalUserMe(BaseModel):
    id: UUID
    username: str
    role: str
    display_name: str | None
    organization_id: UUID | None
    organization_name: str | None
    permissions: dict[str, Any]
    sections: list[str] = Field(
        default_factory=list,
        description="Разрешённые разделы панели для сотрудника; для ролей выше сотрудника — полный набор логики на фронте",
    )


class PortalPasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=6, max_length=256)


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str | None = Field(default=None, max_length=128)
    admin_username: str = Field(min_length=2, max_length=128)
    admin_password: str = Field(min_length=6, max_length=256)
    admin_display_name: str | None = Field(default=None, max_length=255)


class OrganizationPublic(BaseModel):
    id: UUID
    name: str
    slug: str
    is_active: bool
    created_at: datetime


class PortalUserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=128)
    password: str = Field(min_length=6, max_length=256)
    display_name: str | None = Field(default=None, max_length=255)
    role: str = Field(description="director | employee (администратор организации задаётся при создании организации)")
    sections: list[str] = Field(default_factory=list)

    @field_validator("role")
    @classmethod
    def _role_allowed(cls, v: str) -> str:
        if v not in ("director", "employee"):
            raise ValueError("Допустимы только роли director и employee")
        return v

    @field_validator("sections")
    @classmethod
    def _sections(cls, v: list[str]) -> list[str]:
        bad = [s for s in v if s not in ALL_SECTION_KEYS]
        if bad:
            raise ValueError(f"Неизвестные разделы: {bad}")
        return v


class PortalUserPublic(BaseModel):
    id: UUID
    username: str
    role: str
    display_name: str | None
    is_active: bool
    permissions: dict[str, Any]
    created_at: datetime


class PortalUserPatch(BaseModel):
    is_active: bool | None = None
    sections: list[str] | None = None
    display_name: str | None = None

    @field_validator("sections")
    @classmethod
    def _sections(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        bad = [s for s in v if s not in ALL_SECTION_KEYS]
        if bad:
            raise ValueError(f"Неизвестные разделы: {bad}")
        return v


class PortalUserPasswordReset(BaseModel):
    new_password: str = Field(min_length=6, max_length=256)
