"""Маршруты API для лидов."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from src.api.dependencies import CreateLeadUseCaseDep
from src.api.schemas.leads import LeadCreateRequest, LeadResponse, LeadStatusSchema
from src.domain.entities import LeadStatus
from src.domain.exceptions import DomainValidationError

router = APIRouter()


@router.post(
    "",
    response_model=LeadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать лида",
)
async def create_lead(
    body: LeadCreateRequest,
    use_case: CreateLeadUseCaseDep,
) -> LeadResponse:
    """Создаёт нового лида и возвращает его данные с id из БД."""
    domain_status = (
        LeadStatus(body.status.value) if body.status is not None else None
    )
    try:
        lead = await use_case.execute(
            name=body.name,
            phone_number=body.phone_number,
            status=domain_status,
        )
    except DomainValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    if lead.id is None or lead.created_at is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="После сохранения лида отсутствуют id или created_at",
        )
    return LeadResponse(
        id=lead.id,
        name=lead.name,
        phone_number=lead.phone_number,
        status=LeadStatusSchema(lead.status.value),
        created_at=lead.created_at,
    )
