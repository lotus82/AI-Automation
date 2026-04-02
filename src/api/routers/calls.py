"""JSON API: записи звонков и аналитика ОКК."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status
from fastapi.responses import FileResponse

from src.api.dependencies import CallRecordRepositoryDep, SettingsDep
from src.api.schemas.calls import CallAnalyticsItem, CallRecordItem, CallsListResponse
from src.infrastructure.voice.conversation_recording import resolved_recording_file

router = APIRouter(tags=["calls"])


@router.get(
    "/calls",
    response_model=CallsListResponse,
    status_code=status.HTTP_200_OK,
    summary="Список звонков с аналитикой",
)
async def list_calls(
    call_repo: CallRecordRepositoryDep,
    limit: int = Query(default=80, ge=1, le=500),
) -> CallsListResponse:
    """Последние записи из PostgreSQL с присоединённой аналитикой (если воркер уже отработал)."""
    rows = await call_repo.list_recent_with_analytics(limit=limit)
    items: list[CallRecordItem] = []
    for record, analytics in rows:
        if record.id is None:
            continue
        an_out = None
        if analytics is not None and analytics.id is not None:
            an_out = CallAnalyticsItem(
                id=analytics.id,
                score=analytics.score,
                recommendations=analytics.recommendations,
                created_at=analytics.created_at,
            )
        items.append(
            CallRecordItem(
                id=record.id,
                session_id=record.session_id,
                direction=record.direction,
                remote_phone=record.remote_phone,
                duration=record.duration,
                status=record.status,
                transcript_text=record.transcript_text,
                created_at=record.created_at,
                has_audio=bool(record.audio_filename),
                analytics=an_out,
            )
        )
    return CallsListResponse(items=items)


@router.get(
    "/calls/{call_id}/recording",
    status_code=status.HTTP_200_OK,
    summary="Скачать или прослушать WAV записи разговора",
    response_class=FileResponse,
)
async def get_call_recording(
    call_id: UUID,
    call_repo: CallRecordRepositoryDep,
    settings: SettingsDep,
) -> FileResponse:
    record = await call_repo.get_by_id(call_id)
    if record is None or not record.audio_filename:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Запись не найдена")
    base = settings.call_recordings_dir
    if not base:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Хранилище записей отключено")
    path = resolved_recording_file(Path(base), record.audio_filename)
    if path is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Файл записи отсутствует")
    return FileResponse(
        path,
        media_type="audio/wav",
        filename=path.name,
        content_disposition_type="inline",
    )


@router.delete(
    "/calls/{call_id}/recording",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Удалить файл записи разговора",
)
async def delete_call_recording(
    call_id: UUID,
    call_repo: CallRecordRepositoryDep,
    settings: SettingsDep,
) -> Response:
    record = await call_repo.get_by_id(call_id)
    if record is None or not record.audio_filename:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Запись не найдена")
    base = settings.call_recordings_dir
    if base:
        path = resolved_recording_file(Path(base), record.audio_filename)
        if path is not None and path.is_file():
            try:
                path.unlink()
            except OSError:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Не удалось удалить файл",
                ) from None
    await call_repo.update_audio_filename(call_id, None)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
