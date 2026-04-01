"""JSON API: записи звонков и аналитика ОКК."""

from __future__ import annotations

from fastapi import APIRouter, Query, status

from src.api.dependencies import CallRecordRepositoryDep
from src.api.schemas.calls import CallAnalyticsItem, CallRecordItem, CallsListResponse

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
                analytics=an_out,
            )
        )
    return CallsListResponse(items=items)
