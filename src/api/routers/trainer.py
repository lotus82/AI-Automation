"""ИИ-тренер: анализ транскриптов (BANT/MEDDIC) и исходящая голосовая симуляция через ARI."""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from loguru import logger
from sqlalchemy import select

from src.api.dependencies import (
    AsyncSessionDep,
    RedisDep,
    SettingsDep,
    TrainerAIServiceDep,
)
from src.api.schemas.trainer_ai import (
    TrainerAnalyzeRequest,
    TrainerAnalyzeResponse,
    TrainerMethodologyPublic,
    TrainerSimulateRequest,
    TrainerSimulateResponse,
)
from src.domain.trainer_ai_schemas import BantAnalysisResult, MeddicAnalysisResult
from src.infrastructure.models import AiTrainerSessionModel, TrainerMethodologyModel
from src.infrastructure.repositories import SqlAlchemyTrainingScenarioRepository
from src.infrastructure.telephony.ari_client import AriRestClient
from src.infrastructure.training_session_redis import (
    encode_trainer_meta,
    trainer_session_redis_key,
)

router = APIRouter(tags=["trainer"])


@router.get(
    "/trainer/methodologies",
    response_model=list[TrainerMethodologyPublic],
    summary="Список методик (BANT, MEDDIC)",
)
async def list_methodologies(session: AsyncSessionDep) -> list[TrainerMethodologyPublic]:
    r = await session.execute(
        select(TrainerMethodologyModel).order_by(TrainerMethodologyModel.name)
    )
    rows = r.scalars().all()
    return [
        TrainerMethodologyPublic(
            id=row.id,
            code=row.code,
            name=row.name,
            description=(row.description or "").strip(),
        )
        for row in rows
    ]


@router.post(
    "/trainer/analyze",
    response_model=TrainerAnalyzeResponse,
    summary="Пост-анализ транскрипта по BANT или MEDDIC",
)
async def trainer_analyze(
    body: TrainerAnalyzeRequest,
    session: AsyncSessionDep,
    trainer_ai: TrainerAIServiceDep,
) -> TrainerAnalyzeResponse:
    try:
        raw = await trainer_ai.analyze_transcript(body.transcript, body.methodology_code)
    except RuntimeError as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)) from e
    except Exception as e:
        logger.exception("trainer analyze failed")
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail=f"Ошибка LLM: {e!s}",
        ) from e

    meth_row = await session.scalar(
        select(TrainerMethodologyModel).where(
            TrainerMethodologyModel.code == body.methodology_code
        )
    )
    methodology_id = meth_row.id if meth_row else None

    manager_key = (body.manager_id or "panel").strip() or "panel"
    if isinstance(raw, BantAnalysisResult):
        payload = raw.model_dump()
        bant = raw
        meddic = None
        meth_label = "bant"
    else:
        payload = raw.model_dump()
        bant = None
        meddic = raw
        meth_label = "meddic"

    row = AiTrainerSessionModel(
        manager_id=manager_key,
        session_type="analysis",
        result_data=payload,
        methodology_id=methodology_id,
        scenario_id=None,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)

    return TrainerAnalyzeResponse(
        methodology=meth_label,
        bant=bant,
        meddic=meddic,
        saved_session_id=row.id,
    )


@router.post(
    "/trainer/simulate",
    response_model=TrainerSimulateResponse,
    summary="Инициировать исходящий тренировочный звонок (ARI originate)",
)
async def trainer_simulate(
    body: TrainerSimulateRequest,
    session: AsyncSessionDep,
    redis: RedisDep,
    settings: SettingsDep,
) -> TrainerSimulateResponse:
    if not (
        (settings.asterisk_url or "").strip()
        and (settings.asterisk_ari_user or "").strip()
        and (settings.asterisk_ari_password or "").strip()
    ):
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Asterisk ARI не настроен (ASTERISK_URL / учётные данные).",
        )

    repo = SqlAlchemyTrainingScenarioRepository(session)
    sc = await repo.get_by_id(body.scenario_id)
    if sc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Сценарий не найден")
    await session.commit()

    session_id = str(uuid4())
    ttl = settings.chat_memory_ttl_seconds
    await redis.setex(
        trainer_session_redis_key(session_id),
        ttl,
        encode_trainer_meta(
            scenario_id=str(body.scenario_id),
            manager_name=body.manager_phone.strip(),
        ),
    )

    stasis_app = (settings.asterisk_stasis_app or "voice_ai_app").strip()
    endpoint = f"PJSIP/{body.manager_phone.strip()}"
    app_args = f"trainer,{session_id},{body.scenario_id}"

    rest = AriRestClient(
        base_url=settings.asterisk_url or "",
        user=settings.asterisk_ari_user or "",
        password=settings.asterisk_ari_password or "",
    )
    channel_id: str | None = None
    try:
        ch = await rest.originate_channel(
            endpoint=endpoint,
            app=stasis_app,
            app_args=app_args,
            caller_id="AI Trainer",
        )
        channel_id = str(ch.get("id") or "") or None
    except Exception as e:
        logger.exception("ARI originate trainer: {}", e)
        fail_row = AiTrainerSessionModel(
            manager_id=body.manager_phone.strip(),
            session_type="simulation",
            result_data={"error": str(e), "session_id": session_id},
            methodology_id=None,
            scenario_id=body.scenario_id,
        )
        session.add(fail_row)
        await session.commit()
        await rest.aclose()
        return TrainerSimulateResponse(
            status="error",
            session_id=session_id,
            channel_id=None,
            message=f"Не удалось инициировать вызов: {e!s}",
        )
    await rest.aclose()

    ok_row = AiTrainerSessionModel(
        manager_id=body.manager_phone.strip(),
        session_type="simulation",
        result_data={
            "session_id": session_id,
            "channel_id": channel_id,
            "scenario_id": str(body.scenario_id),
            "ari_endpoint": endpoint,
        },
        methodology_id=None,
        scenario_id=body.scenario_id,
    )
    session.add(ok_row)
    await session.commit()

    return TrainerSimulateResponse(
        status="initiated",
        session_id=session_id,
        channel_id=channel_id,
        message="Вызов передан в Asterisk; при ответе менеджера поднимется Pipecat в режиме тренажёра.",
    )
