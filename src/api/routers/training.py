"""REST API сценариев тренажёра."""

from __future__ import annotations

from fastapi import APIRouter, status

from src.api.dependencies import TrainingScenarioRepositoryDep
from src.api.schemas.training import TrainingScenarioCreate, TrainingScenarioResponse
from src.domain.entities import TrainingScenario

router = APIRouter()


@router.get(
    "/scenarios",
    response_model=list[TrainingScenarioResponse],
    status_code=status.HTTP_200_OK,
    summary="Список сценариев тренажёра",
)
async def list_scenarios(
    repo: TrainingScenarioRepositoryDep,
) -> list[TrainingScenarioResponse]:
    """Все сценарии (новые сверху) для выпадающего списка и админки."""
    rows = await repo.list_recent(limit=200)
    out: list[TrainingScenarioResponse] = []
    for r in rows:
        if r.id is None:
            continue
        out.append(
            TrainingScenarioResponse(
                id=r.id,
                title=r.title,
                client_persona_prompt=r.client_persona_prompt,
                objections_to_raise=r.objections_to_raise,
                created_at=r.created_at,
            )
        )
    return out


@router.post(
    "/scenarios",
    response_model=TrainingScenarioResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать сценарий",
)
async def create_scenario(
    body: TrainingScenarioCreate,
    repo: TrainingScenarioRepositoryDep,
) -> TrainingScenarioResponse:
    """Создаёт персону клиента и возражения для тренировки менеджеров."""
    entity = TrainingScenario(
        title=body.title.strip(),
        client_persona_prompt=body.client_persona_prompt.strip(),
        objections_to_raise=body.objections_to_raise.strip(),
    )
    saved = await repo.save(entity)
    if saved.id is None:
        msg = "После сохранения сценария отсутствует id"
        raise RuntimeError(msg)
    return TrainingScenarioResponse(
        id=saved.id,
        title=saved.title,
        client_persona_prompt=saved.client_persona_prompt,
        objections_to_raise=saved.objections_to_raise,
        created_at=saved.created_at,
    )
