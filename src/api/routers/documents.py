"""Модуль «Читатель»: CRUD документов, узлы дерева, загрузка .txt, публичное API для Mini App."""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select, update
from starlette.responses import Response

from src.api.dependencies import AsyncSessionDep
from src.api.dependencies_portal import PortalUserDep
from src.api.org_scope import resolve_organization_scope
from src.domain.portal_roles import ROLE_SUPER_ADMIN
from src.infrastructure.models import DocumentModel, DocumentNodeModel, OrganizationModel
from src.infrastructure.services.document_parser_service import DocumentParserService
from src.infrastructure.services.text_file_decoding import decode_txt_bytes

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])
public_router = APIRouter(prefix="/public/documents", tags=["documents-public"])

_MAX_TXT_BYTES = 40 * 1024 * 1024
_BULK_CHUNK = 500


def _resolve_org_scope(user, organization_id: UUID | None) -> UUID:
    scope = resolve_organization_scope(user, organization_id)
    if scope is None:
        if user.role == ROLE_SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Для супер-админа нужно указать organization_id",
            )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет организации")
    return scope


async def _get_document_org(session: AsyncSessionDep, doc_id: UUID, org_id: UUID) -> DocumentModel:
    row = await session.get(DocumentModel, doc_id)
    if row is None or row.organization_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Документ не найден")
    return row


# --- Схемы -------------------------------------------------------------------


class DocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    author: str | None = Field(default=None, max_length=512)
    description: str | None = None


class DocumentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=512)
    author: str | None = Field(default=None, max_length=512)
    description: str | None = None


class DocumentOut(BaseModel):
    id: UUID
    organization_id: UUID
    title: str
    author: str | None
    description: str | None
    created_at: datetime
    updated_at: datetime


class NodeOut(BaseModel):
    id: UUID
    document_id: UUID
    parent_id: UUID | None
    title: str
    content: str | None
    node_type: str
    order_index: int
    children: list["NodeOut"] = Field(default_factory=list)


NodeOut.model_rebuild()


class NodeUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=512)
    content: str | None = None
    order_index: int | None = Field(default=None, ge=0, le=10_000_000)


class PublicDocumentBundle(BaseModel):
    document: DocumentOut
    tree: list[NodeOut]


def _doc_to_out(row: DocumentModel) -> DocumentOut:
    return DocumentOut(
        id=row.id,
        organization_id=row.organization_id,
        title=row.title,
        author=(row.author or "").strip() or None,
        description=row.description,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _node_to_out(n: DocumentNodeModel, children: list[NodeOut]) -> NodeOut:
    return NodeOut(
        id=n.id,
        document_id=n.document_id,
        parent_id=n.parent_id,
        title=n.title,
        content=n.content,
        node_type=n.node_type,
        order_index=int(n.order_index or 0),
        children=children,
    )


def _build_tree(rows: list[DocumentNodeModel]) -> list[NodeOut]:
    by_parent: dict[UUID | None, list[DocumentNodeModel]] = {}
    for n in rows:
        by_parent.setdefault(n.parent_id, []).append(n)
    for lst in by_parent.values():
        lst.sort(key=lambda x: (int(x.order_index or 0), str(x.title)))

    def walk(pid: UUID | None) -> list[NodeOut]:
        out: list[NodeOut] = []
        for n in by_parent.get(pid, []):
            out.append(_node_to_out(n, walk(n.id)))
        return out

    return walk(None)


# --- CRUD документ -----------------------------------------------------------


@router.get("", response_model=list[DocumentOut])
async def list_documents(
    user: PortalUserDep,
    session: AsyncSessionDep,
    organization_id: UUID | None = Query(default=None),
) -> list[DocumentOut]:
    org_id = _resolve_org_scope(user, organization_id)
    rows = (
        await session.execute(
            select(DocumentModel).where(DocumentModel.organization_id == org_id).order_by(DocumentModel.updated_at.desc()),
        )
    ).scalars().all()
    return [_doc_to_out(r) for r in rows]


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def create_document(
    body: DocumentCreate,
    user: PortalUserDep,
    session: AsyncSessionDep,
    organization_id: UUID | None = Query(default=None),
) -> DocumentOut:
    org_id = _resolve_org_scope(user, organization_id)
    org = await session.get(OrganizationModel, org_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Организация не найдена")
    row = DocumentModel(
        organization_id=org_id,
        title=body.title.strip(),
        author=(body.author or "").strip() or None,
        description=body.description,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _doc_to_out(row)


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: UUID,
    user: PortalUserDep,
    session: AsyncSessionDep,
    organization_id: UUID | None = Query(default=None),
) -> DocumentOut:
    org_id = _resolve_org_scope(user, organization_id)
    row = await _get_document_org(session, document_id, org_id)
    return _doc_to_out(row)


@router.put("/{document_id}", response_model=DocumentOut)
async def update_document(
    document_id: UUID,
    body: DocumentUpdate,
    user: PortalUserDep,
    session: AsyncSessionDep,
    organization_id: UUID | None = Query(default=None),
) -> DocumentOut:
    org_id = _resolve_org_scope(user, organization_id)
    row = await _get_document_org(session, document_id, org_id)
    if body.title is not None:
        row.title = body.title.strip()
    if body.author is not None:
        row.author = body.author.strip() or None
    if body.description is not None:
        row.description = body.description
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _doc_to_out(row)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    user: PortalUserDep,
    session: AsyncSessionDep,
    organization_id: UUID | None = Query(default=None),
) -> Response:
    org_id = _resolve_org_scope(user, organization_id)
    row = await _get_document_org(session, document_id, org_id)
    await session.delete(row)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Узлы --------------------------------------------------------------------


@router.get("/{document_id}/nodes", response_model=list[NodeOut])
async def list_nodes_flat(
    document_id: UUID,
    user: PortalUserDep,
    session: AsyncSessionDep,
    organization_id: UUID | None = Query(default=None),
    nested: bool = Query(default=False, description="true — вложенное дерево"),
) -> list[NodeOut]:
    org_id = _resolve_org_scope(user, organization_id)
    await _get_document_org(session, document_id, org_id)
    rows = (
        await session.execute(
            select(DocumentNodeModel)
            .where(DocumentNodeModel.document_id == document_id)
            .order_by(DocumentNodeModel.order_index.asc()),
        )
    ).scalars().all()
    if nested:
        return _build_tree(list(rows))
    return [
        NodeOut(
            id=n.id,
            document_id=n.document_id,
            parent_id=n.parent_id,
            title=n.title,
            content=n.content,
            node_type=n.node_type,
            order_index=int(n.order_index or 0),
            children=[],
        )
        for n in rows
    ]


@router.put("/{document_id}/nodes/{node_id}", response_model=NodeOut)
async def update_node(
    document_id: UUID,
    node_id: UUID,
    body: NodeUpdate,
    user: PortalUserDep,
    session: AsyncSessionDep,
    organization_id: UUID | None = Query(default=None),
) -> NodeOut:
    org_id = _resolve_org_scope(user, organization_id)
    await _get_document_org(session, document_id, org_id)
    n = await session.get(DocumentNodeModel, node_id)
    if n is None or n.document_id != document_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Узел не найден")
    if body.title is not None:
        n.title = body.title.strip()
    if body.content is not None:
        n.content = body.content
    if body.order_index is not None:
        n.order_index = int(body.order_index)
    session.add(n)
    await session.commit()
    await session.refresh(n)
    return NodeOut(
        id=n.id,
        document_id=n.document_id,
        parent_id=n.parent_id,
        title=n.title,
        content=n.content,
        node_type=n.node_type,
        order_index=int(n.order_index or 0),
        children=[],
    )


# --- Загрузка TXT ------------------------------------------------------------


@router.post("/{document_id}/upload", response_model=DocumentOut)
async def upload_document_txt(
    document_id: UUID,
    user: PortalUserDep,
    session: AsyncSessionDep,
    file: UploadFile = File(...),
    organization_id: UUID | None = Query(default=None),
) -> DocumentOut:
    org_id = _resolve_org_scope(user, organization_id)
    row = await _get_document_org(session, document_id, org_id)
    if not (file.filename or "").lower().endswith(".txt"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ожидается файл .txt")
    raw = await file.read()
    if len(raw) > _MAX_TXT_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Файл больше 40 МБ")
    text = decode_txt_bytes(raw)
    try:
        nodes = DocumentParserService.parse_text(document_id, text)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    await session.execute(delete(DocumentNodeModel).where(DocumentNodeModel.document_id == document_id))
    for i in range(0, len(nodes), _BULK_CHUNK):
        chunk = nodes[i : i + _BULK_CHUNK]
        session.add_all(chunk)
        await session.flush()

    await session.execute(
        update(DocumentModel).where(DocumentModel.id == document_id).values(updated_at=func.now()),
    )
    await session.commit()
    await session.refresh(row)
    return _doc_to_out(row)


# --- Публичное API (Mini App) ------------------------------------------------


@public_router.get("/{document_id}", response_model=PublicDocumentBundle)
async def get_public_document_tree(document_id: UUID, session: AsyncSessionDep) -> PublicDocumentBundle:
    row = await session.get(DocumentModel, document_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Документ не найден")
    nodes = (
        await session.execute(
            select(DocumentNodeModel).where(DocumentNodeModel.document_id == document_id),
        )
    ).scalars().all()
    tree = _build_tree(list(nodes))
    return PublicDocumentBundle(document=_doc_to_out(row), tree=tree)
