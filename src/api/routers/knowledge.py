"""Загрузка и управление базой знаний (TXT, XLSX) для RAG."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Response, UploadFile, status

from src.api.dependencies import (
    AsyncSessionDep,
    EmbeddingServiceDep,
    KnowledgeRepositoryDep,
)
from src.api.schemas.knowledge import (
    KnowledgeItemResponse,
    KnowledgeUploadCreatedItem,
    KnowledgeUploadResponse,
)
from src.domain.entities import KnowledgeItem
from src.infrastructure.knowledge_ingest import ingest_upload

router = APIRouter(tags=["knowledge"])

_MAX_UPLOAD_BYTES = 15 * 1024 * 1024
_PREVIEW_LEN = 220


def _preview(content: str) -> str:
    s = (content or "").replace("\n", " ").replace("\t", " ").strip()
    if len(s) <= _PREVIEW_LEN:
        return s
    return s[: _PREVIEW_LEN] + "…"


def _embedding_ok(vec: list[float] | None) -> bool:
    if not vec:
        return False
    return any(abs(x) > 1e-9 for x in vec[:48])


@router.get(
    "/knowledge/items",
    response_model=list[KnowledgeItemResponse],
    status_code=status.HTTP_200_OK,
    summary="Список элементов базы знаний",
)
async def list_knowledge_items(
    repo: KnowledgeRepositoryDep,
) -> list[KnowledgeItemResponse]:
    rows = await repo.list_recent(limit=500)
    out: list[KnowledgeItemResponse] = []
    for r in rows:
        if r.id is None:
            continue
        out.append(
            KnowledgeItemResponse(
                id=r.id,
                title=r.title,
                content_preview=_preview(r.content),
                has_embedding=_embedding_ok(r.embedding),
                created_at=r.created_at,
            )
        )
    return out


@router.post(
    "/knowledge/upload",
    response_model=KnowledgeUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Загрузить .txt или .xlsx в базу знаний",
)
async def upload_knowledge(
    session: AsyncSessionDep,
    repo: KnowledgeRepositoryDep,
    embedding: EmbeddingServiceDep,
    files: list[UploadFile] = File(
        ...,
        description="Один или несколько файлов .txt / .xlsx",
    ),
) -> KnowledgeUploadResponse:
    if not files:
        raise HTTPException(status_code=400, detail="Добавьте хотя бы один файл")
    created: list[KnowledgeUploadCreatedItem] = []
    for uf in files:
        raw = await uf.read()
        if len(raw) > _MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Файл «{uf.filename}» больше {_MAX_UPLOAD_BYTES // (1024 * 1024)} МБ",
            )
        name = (uf.filename or "upload").strip()
        try:
            pairs = ingest_upload(raw=raw, filename=name)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        if not pairs:
            continue
        for title, content in pairs:
            emb = await embedding.generate_embedding(content)
            saved = await repo.save(
                KnowledgeItem(title=title, content=content, embedding=emb),
            )
            if saved.id is None:
                msg = "Не удалось получить id после сохранения"
                raise RuntimeError(msg)
            created.append(KnowledgeUploadCreatedItem(id=saved.id, title=saved.title))
    await session.commit()
    return KnowledgeUploadResponse(created_count=len(created), items=created)


@router.delete(
    "/knowledge/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Удалить элемент базы знаний",
)
async def delete_knowledge_item(
    item_id: UUID,
    session: AsyncSessionDep,
    repo: KnowledgeRepositoryDep,
) -> Response:
    ok = await repo.delete_by_id(item_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
