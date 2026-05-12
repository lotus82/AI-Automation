"""Комплаенс и секретариат (Legal & Reporting): профиль, сроки, документы.

Мультитенантность: все сущности по ``organization_id``; область задаётся
``resolve_organization_scope`` (+ query ``organization_id`` для супер-админа).

Миграция БД: см. ``alembic/versions/054_compl_module.py``.
  Применить: ``alembic upgrade head``
  Сгенерировать свою (альтернатива): ``alembic revision --autogenerate -m "compliance legal"``
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from starlette.responses import Response

from src.api.dependencies import AsyncSessionDep, RedisDep, SettingsDep
from src.api.dependencies_portal import PortalUserDep
from src.api.org_scope import resolve_organization_scope
from src.api.schemas.compliance import (
    ComplianceDeadlineResponse,
    ComplianceDocumentGenerateRequest,
    ComplianceDocumentGenerateResponse,
    LegalDocumentCreate,
    LegalDocumentResponse,
    LegalDocumentSummary,
    LegalDocumentUpdate,
    LegalProfileResponse,
    LegalProfileUpsert,
)
from src.domain.portal_roles import ROLE_SUPER_ADMIN
from src.infrastructure.models import LegalDocStatus
from src.infrastructure.repositories.compliance_repositories import (
    SqlAlchemyComplianceDeadlineRepository,
    SqlAlchemyLegalDocumentRepository,
    SqlAlchemyLegalProfileRepository,
)
from src.infrastructure.services.legal_ai import LegalAIService
from src.infrastructure.services.legal_document_docx import markdown_to_docx_bytes

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/compliance", tags=["compliance"])


def _attendees_from_context(ctx: dict[str, Any]) -> str:
    raw = ctx.get("attendees")
    if raw is None:
        return str(ctx.get("участники") or ctx.get("participants") or "").strip()
    if isinstance(raw, str):
        return raw.strip()
    if isinstance(raw, list):
        parts: list[str] = []
        for item in raw:
            if isinstance(item, dict):
                name = str(item.get("name") or item.get("fio") or "").strip()
                role = str(item.get("role") or item.get("position") or "").strip()
                parts.append(f"{name} ({role})" if role else name)
            else:
                parts.append(str(item))
        return "; ".join(p for p in parts if p).strip()
    return str(raw).strip()


def _require_organization_id(user: PortalUserDep, organization_id: UUID | None) -> UUID:
    scope = resolve_organization_scope(user, organization_id)
    if scope is None:
        if user.role == ROLE_SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Для супер-админа нужно указать organization_id",
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет доступа к данным организации",
        )
    return scope


@router.get("/profile", response_model=LegalProfileResponse)
async def get_legal_profile(
    user: PortalUserDep,
    session: AsyncSessionDep,
    organization_id: UUID | None = Query(
        None,
        description="Супер-админ: id организации",
    ),
) -> LegalProfileResponse:
    oid = _require_organization_id(user, organization_id)
    repo = SqlAlchemyLegalProfileRepository(session, organization_id=oid)
    row = await repo.get()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Профиль не создан")
    return LegalProfileResponse.model_validate(row)


@router.put("/profile", response_model=LegalProfileResponse)
async def put_legal_profile(
    body: LegalProfileUpsert,
    user: PortalUserDep,
    session: AsyncSessionDep,
    organization_id: UUID | None = Query(
        None,
        description="Супер-админ: id организации",
    ),
) -> LegalProfileResponse:
    oid = _require_organization_id(user, organization_id)
    repo = SqlAlchemyLegalProfileRepository(session, organization_id=oid)
    row = await repo.upsert(
        org_type=body.org_type,
        tax_system=body.tax_system,
        general_director_name=body.general_director_name,
        charter_rules=body.charter_rules,
        system_role_id=body.system_role_id,
        knowledge_item_ids=body.knowledge_item_ids,
    )
    return LegalProfileResponse.model_validate(row)


@router.get("/deadlines", response_model=list[ComplianceDeadlineResponse])
async def list_compliance_deadlines(
    user: PortalUserDep,
    session: AsyncSessionDep,
    organization_id: UUID | None = Query(
        None,
        description="Супер-админ: id организации",
    ),
) -> list[ComplianceDeadlineResponse]:
    oid = _require_organization_id(user, organization_id)
    repo = SqlAlchemyComplianceDeadlineRepository(session, organization_id=oid)
    rows = await repo.list_all()
    return [ComplianceDeadlineResponse.model_validate(r) for r in rows]


@router.get("/documents", response_model=list[LegalDocumentSummary])
async def list_legal_documents(
    user: PortalUserDep,
    session: AsyncSessionDep,
    organization_id: UUID | None = Query(
        None,
        description="Супер-админ: id организации",
    ),
) -> list[LegalDocumentSummary]:
    oid = _require_organization_id(user, organization_id)
    repo = SqlAlchemyLegalDocumentRepository(session, organization_id=oid)
    rows = await repo.list_recent()
    return [LegalDocumentSummary.model_validate(r) for r in rows]


@router.get("/documents/{document_id}", response_model=LegalDocumentResponse)
async def get_legal_document(
    document_id: UUID,
    user: PortalUserDep,
    session: AsyncSessionDep,
    organization_id: UUID | None = Query(
        None,
        description="Супер-админ: id организации",
    ),
) -> LegalDocumentResponse:
    oid = _require_organization_id(user, organization_id)
    repo = SqlAlchemyLegalDocumentRepository(session, organization_id=oid)
    row = await repo.get_by_id(document_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Документ не найден")
    return LegalDocumentResponse.model_validate(row)


@router.get("/documents/{document_id}/docx")
async def export_legal_document_docx(
    document_id: UUID,
    user: PortalUserDep,
    session: AsyncSessionDep,
    organization_id: UUID | None = Query(
        None,
        description="Супер-админ: id организации",
    ),
) -> Response:
    """Экспорт содержимого документа (Markdown) в Word (.docx)."""

    from urllib.parse import quote

    import re

    oid = _require_organization_id(user, organization_id)
    repo = SqlAlchemyLegalDocumentRepository(session, organization_id=oid)
    row = await repo.get_by_id(document_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Документ не найден")

    doc_bytes = markdown_to_docx_bytes(row.content or "", title=row.title)
    raw_title = (row.title or "document").strip()
    ascii_fallback = re.sub(r"[^A-Za-z0-9._-]+", "_", raw_title).strip("._") or "legal_document"
    if not ascii_fallback.lower().endswith(".docx"):
        ascii_fallback = f"{ascii_fallback[:120]}.docx"
    utf_name = f"{raw_title[:180]}.docx" if not raw_title.lower().endswith(".docx") else raw_title[:200]
    disp = (
        f'attachment; filename="{ascii_fallback}"; '
        f"filename*=UTF-8''{quote(utf_name, safe='')}"
    )
    return Response(
        content=doc_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": disp},
    )


@router.post("/documents/generate", response_model=ComplianceDocumentGenerateResponse)
async def generate_compliance_document(
    body: ComplianceDocumentGenerateRequest,
    user: PortalUserDep,
    session: AsyncSessionDep,
    redis: RedisDep,
    settings: SettingsDep,
    organization_id: UUID | None = Query(
        None,
        description="Супер-админ: id организации",
    ),
) -> ComplianceDocumentGenerateResponse:
    """Черновик протокола/документа через LLM с инструментами Гаранта и правил устава."""

    oid = _require_organization_id(user, organization_id)
    ctx = body.context if isinstance(body.context, dict) else {}
    agenda = str(ctx.get("agenda") or ctx.get("повестка") or "").strip()
    attendees = _attendees_from_context(ctx)

    svc = LegalAIService(settings)
    try:
        text, doc_row = await svc.generate_protocol(
            session=session,
            redis=redis,
            organization_id=oid,
            agenda=agenda,
            attendees=attendees,
            role_id=body.role_id,
            document_type_key=body.type.strip(),
            extra_context=ctx,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc).strip()
            or "Сервис языковой модели недоступен: проверьте ключи в настройках организации.",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Ошибка генерации юридического документа для org=%s", oid)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось сгенерировать документ. Обратитесь к администратору или повторите запрос позже.",
        ) from exc

    return ComplianceDocumentGenerateResponse(
        content=text,
        document_id=doc_row.id,
        detail=None,
    )


@router.post("/documents", response_model=LegalDocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_legal_document(
    body: LegalDocumentCreate,
    user: PortalUserDep,
    session: AsyncSessionDep,
    organization_id: UUID | None = Query(
        None,
        description="Супер-админ: id организации",
    ),
) -> LegalDocumentResponse:
    oid = _require_organization_id(user, organization_id)
    repo = SqlAlchemyLegalDocumentRepository(session, organization_id=oid)
    st = LegalDocStatus.DRAFT if body.status is None else body.status
    row = await repo.create(
        title=body.title,
        doc_type=body.doc_type,
        content=body.content,
        status=st,
    )
    return LegalDocumentResponse.model_validate(row)


@router.put("/documents/{document_id}", response_model=LegalDocumentResponse)
async def update_legal_document(
    document_id: UUID,
    body: LegalDocumentUpdate,
    user: PortalUserDep,
    session: AsyncSessionDep,
    organization_id: UUID | None = Query(
        None,
        description="Супер-админ: id организации",
    ),
) -> LegalDocumentResponse:
    oid = _require_organization_id(user, organization_id)
    repo = SqlAlchemyLegalDocumentRepository(session, organization_id=oid)
    row = await repo.update(
        document_id,
        title=body.title,
        doc_type=body.doc_type,
        content=body.content,
        status=body.status,
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Документ не найден")
    return LegalDocumentResponse.model_validate(row)