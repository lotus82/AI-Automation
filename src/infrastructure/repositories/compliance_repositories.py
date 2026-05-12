"""Репозитории модуля «Комплаенс и секретариат» (SQLAlchemy async)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.models import (
    ComplianceDeadlineModel,
    LegalDocumentModel,
    LegalDocStatus,
    LegalDocType,
    LegalOrgType,
    LegalProfileModel,
    LegalTaxSystem,
)


class SqlAlchemyLegalProfileRepository:
    """Один профиль на организацию (UNIQUE organization_id)."""

    def __init__(self, session: AsyncSession, *, organization_id: UUID) -> None:
        self._session = session
        self._organization_id = organization_id

    async def get(self) -> LegalProfileModel | None:
        res = await self._session.execute(
            select(LegalProfileModel).where(
                LegalProfileModel.organization_id == self._organization_id,
            ),
        )
        return res.scalar_one_or_none()

    async def upsert(
        self,
        *,
        org_type: LegalOrgType,
        tax_system: LegalTaxSystem,
        general_director_name: str,
        charter_rules: dict[str, Any],
        system_role_id: str | None = None,
        knowledge_item_ids: list[UUID] | None = None,
    ) -> LegalProfileModel:
        kid = [str(x) for x in (knowledge_item_ids or [])]
        role_key = (system_role_id or "").strip() or None
        row = await self.get()
        if row is None:
            row = LegalProfileModel(
                organization_id=self._organization_id,
                org_type=org_type,
                tax_system=tax_system,
                general_director_name=general_director_name.strip(),
                charter_rules=charter_rules or {},
                system_role_id=role_key,
                knowledge_item_ids=kid,
            )
            self._session.add(row)
        else:
            row.org_type = org_type
            row.tax_system = tax_system
            row.general_director_name = general_director_name.strip()
            row.charter_rules = charter_rules or {}
            row.system_role_id = role_key
            row.knowledge_item_ids = kid
        await self._session.flush()
        await self._session.refresh(row)
        return row


class SqlAlchemyComplianceDeadlineRepository:
    """Сроки соблюдения требований по организации."""

    def __init__(self, session: AsyncSession, *, organization_id: UUID) -> None:
        self._session = session
        self._organization_id = organization_id

    async def list_all(self, *, limit: int = 500) -> list[ComplianceDeadlineModel]:
        res = await self._session.execute(
            select(ComplianceDeadlineModel)
            .where(ComplianceDeadlineModel.organization_id == self._organization_id)
            .order_by(ComplianceDeadlineModel.due_date.asc(), ComplianceDeadlineModel.title.asc())
            .limit(limit),
        )
        return list(res.scalars().all())


class SqlAlchemyLegalDocumentRepository:
    """Юридические документы (протоколы, отчёты)."""

    def __init__(self, session: AsyncSession, *, organization_id: UUID) -> None:
        self._session = session
        self._organization_id = organization_id

    async def list_recent(self, *, limit: int = 200) -> list[LegalDocumentModel]:
        res = await self._session.execute(
            select(LegalDocumentModel)
            .where(LegalDocumentModel.organization_id == self._organization_id)
            .order_by(LegalDocumentModel.updated_at.desc())
            .limit(limit),
        )
        return list(res.scalars().all())

    async def get_by_id(self, doc_id: UUID) -> LegalDocumentModel | None:
        res = await self._session.execute(
            select(LegalDocumentModel).where(
                LegalDocumentModel.id == doc_id,
                LegalDocumentModel.organization_id == self._organization_id,
            ),
        )
        return res.scalar_one_or_none()

    async def create(
        self,
        *,
        title: str,
        doc_type: LegalDocType,
        content: str,
        status: LegalDocStatus = LegalDocStatus.DRAFT,
    ) -> LegalDocumentModel:
        row = LegalDocumentModel(
            organization_id=self._organization_id,
            title=title.strip(),
            doc_type=doc_type,
            content=content or "",
            status=status,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return row

    async def update(
        self,
        doc_id: UUID,
        *,
        title: str | None = None,
        doc_type: LegalDocType | None = None,
        content: str | None = None,
        status: LegalDocStatus | None = None,
    ) -> LegalDocumentModel | None:
        row = await self.get_by_id(doc_id)
        if row is None:
            return None
        if title is not None:
            row.title = title.strip()
        if doc_type is not None:
            row.doc_type = doc_type
        if content is not None:
            row.content = content
        if status is not None:
            row.status = status
        await self._session.flush()
        await self._session.refresh(row)
        return row
