"""API очереди автообзвона и запуска кампании Celery."""

from __future__ import annotations

from fastapi import APIRouter, File, UploadFile, status

from src.api.dependencies import DialerQueueRepositoryDep
from src.api.schemas.dialer import DialerCampaignStartResponse, DialerUploadResponse
from src.infrastructure.phone_list_upload import extract_phones_from_upload
from src.workers.tasks import run_outbound_campaign_task

router = APIRouter(tags=["dialer"])


@router.post(
    "/dialer/queue/upload",
    response_model=DialerUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Загрузить номера (CSV или XLSX, первая колонка)",
)
async def dialer_queue_upload(
    repo: DialerQueueRepositoryDep,
    file: UploadFile = File(..., description="Файл .csv или .xlsx"),
) -> DialerUploadResponse:
    """Добавляет строки в dialer_queue со статусом pending."""
    phones = await extract_phones_from_upload(file)
    inserted = await repo.add_phones(phones)
    return DialerUploadResponse(inserted=inserted)


@router.post(
    "/dialer/campaign/start",
    response_model=DialerCampaignStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Запустить обработку очереди (Celery)",
)
async def dialer_campaign_start() -> DialerCampaignStartResponse:
    """Ставит в очередь задачу обхода pending-номеров и вызовов через ITelephonyService."""
    run_outbound_campaign_task.delay()
    return DialerCampaignStartResponse(status="queued")
