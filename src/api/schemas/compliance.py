"""Схемы API «Комплаенс и секретариат»."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from src.infrastructure.models import (
    ComplianceDeadlineStatus,
    LegalDocStatus,
    LegalDocType,
    LegalOrgType,
    LegalTaxSystem,
)


class LegalProfileResponse(BaseModel):
    id: UUID
    organization_id: UUID
    org_type: LegalOrgType
    tax_system: LegalTaxSystem
    general_director_name: str
    charter_rules: dict[str, Any]
    system_role_id: str | None = None
    knowledge_item_ids: list[UUID] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("system_role_id", mode="before")
    @classmethod
    def _coerce_system_role_id(cls, v: Any) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        return s or None

    @field_validator("knowledge_item_ids", mode="before")
    @classmethod
    def _coerce_knowledge_ids(cls, v: Any) -> list[UUID]:
        if v is None:
            return []
        if not isinstance(v, list):
            return []
        out: list[UUID] = []
        for x in v:
            try:
                out.append(x if isinstance(x, UUID) else UUID(str(x).strip()))
            except ValueError:
                continue
        return out


class LegalProfileUpsert(BaseModel):
    org_type: LegalOrgType
    tax_system: LegalTaxSystem
    general_director_name: str = Field(max_length=512)
    charter_rules: dict[str, Any] = Field(default_factory=dict)
    system_role_id: str | None = Field(default=None, max_length=128)
    knowledge_item_ids: list[UUID] = Field(default_factory=list)

    @field_validator("system_role_id", mode="before")
    @classmethod
    def _strip_system_role_id(cls, v: Any) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        return s or None


class ComplianceDeadlineResponse(BaseModel):
    id: UUID
    organization_id: UUID
    title: str
    due_date: date
    status: ComplianceDeadlineStatus
    description: str

    model_config = {"from_attributes": True}


class LegalDocumentSummary(BaseModel):
    id: UUID
    organization_id: UUID
    title: str
    doc_type: LegalDocType
    status: LegalDocStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LegalDocumentResponse(BaseModel):
    id: UUID
    organization_id: UUID
    title: str
    doc_type: LegalDocType
    content: str
    status: LegalDocStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LegalDocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    doc_type: LegalDocType
    content: str = ""
    status: LegalDocStatus | None = LegalDocStatus.DRAFT


class ComplianceDocumentGenerateRequest(BaseModel):
    """Тело ``POST …/documents/generate``."""

    type: str = Field(
        min_length=1,
        max_length=128,
        description="Тип документа (например protocol_director_change)",
    )
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Данные собрания: agenda, attendees, дата и т.д.",
    )
    role_id: UUID | None = Field(
        default=None,
        description="Опционально: UUID роли из SYSTEM_ROLES_CONFIG для системного промпта",
    )


class ComplianceDocumentGenerateResponse(BaseModel):
    """Ответ генерации черновика."""

    content: str
    document_id: UUID
    detail: str | None = Field(
        default=None,
        description="Пояснение (напр. когда API законодательства в демо-режиме)",
    )


class LegalDocumentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=512)
    doc_type: LegalDocType | None = None
    content: str | None = None
    status: LegalDocStatus | None = None
