"""REST API v1: универсальные интеграции с внешними системами."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Response, status

from src.domain.entities.integration import Integration
from src.domain.exceptions.integration_exceptions import (
    ActionNotFoundError,
    IntegrationCallError,
    IntegrationNotFoundError,
)
from src.presentation.api.dependencies.integration_deps import (
    ExecuteActionUseCaseDep,
    IntegrationRepositoryDep,
)
from src.presentation.api.schemas.integration_schemas import (
    ActionExecutionRequest,
    IntegrationCreateRequest,
    IntegrationResponse,
    IntegrationUpdateRequest,
)

router = APIRouter(prefix="/v1/integrations", tags=["Integrations"])


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=IntegrationResponse)
async def create_integration(
    body: IntegrationCreateRequest,
    repo: IntegrationRepositoryDep,
) -> IntegrationResponse:
    now = _utc_now()
    entity = Integration(
        id=uuid4(),
        name=body.name,
        base_url=body.base_url,
        auth=body.auth,
        actions=list(body.actions),
        webhooks=list(body.webhooks),
        created_at=now,
        updated_at=now,
    )
    created = await repo.create(entity)
    return IntegrationResponse.model_validate(created)


@router.get("", response_model=list[IntegrationResponse])
async def list_integrations(repo: IntegrationRepositoryDep) -> list[IntegrationResponse]:
    items = await repo.list_all()
    return [IntegrationResponse.model_validate(x) for x in items]


@router.get("/{integration_id}", response_model=IntegrationResponse)
async def get_integration(
    integration_id: UUID,
    repo: IntegrationRepositoryDep,
) -> IntegrationResponse:
    try:
        entity = await repo.get_by_id(integration_id)
    except IntegrationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Интеграция не найдена") from None
    return IntegrationResponse.model_validate(entity)


@router.put("/{integration_id}", response_model=IntegrationResponse)
async def update_integration(
    integration_id: UUID,
    body: IntegrationUpdateRequest,
    repo: IntegrationRepositoryDep,
) -> IntegrationResponse:
    try:
        existing = await repo.get_by_id(integration_id)
    except IntegrationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Интеграция не найдена") from None
    now = _utc_now()
    entity = Integration(
        id=existing.id,
        name=body.name,
        base_url=body.base_url,
        auth=body.auth,
        actions=list(body.actions),
        webhooks=list(body.webhooks),
        created_at=existing.created_at,
        updated_at=now,
    )
    updated = await repo.update(entity)
    return IntegrationResponse.model_validate(updated)


@router.delete("/{integration_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_integration(
    integration_id: UUID,
    repo: IntegrationRepositoryDep,
) -> Response:
    try:
        await repo.delete(integration_id)
    except IntegrationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Интеграция не найдена") from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{integration_id}/execute")
async def execute_integration_action(
    integration_id: UUID,
    req: ActionExecutionRequest,
    use_case: ExecuteActionUseCaseDep,
) -> Any:
    try:
        return await use_case.execute(integration_id, req.action_name, req.input_params)
    except IntegrationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Интеграция не найдена") from None
    except ActionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Действие не найдено: {req.action_name}",
        ) from None
    except IntegrationCallError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
