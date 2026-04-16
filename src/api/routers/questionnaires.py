"""Опросники: CRUD с вложенными вопросами/вариантами и ИИ-оценка."""

from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from loguru import logger
from redis.asyncio import Redis
from starlette.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.dependencies import AsyncSessionDep, QuestionnaireLLMServiceDep, RedisDep, SettingsDep
from src.api.dependencies_portal import PortalUserDep
from src.api.org_scope import resolve_organization_scope
from src.domain.portal_roles import ROLE_SUPER_ADMIN
from src.api.schemas.questionnaires import (
    AssessRequest,
    AssessResponse,
    QuestionnaireCreate,
    QuestionnaireListItem,
    QuestionnairePublic,
    QuestionnaireUpdate,
    QuestionnaireVerdictPdfBody,
    QuestionOptionPublic,
    QuestionPublic,
)
from src.domain import system_setting_keys as sk
from src.infrastructure.models import QuestionnaireModel, QuestionModel, QuestionOptionModel
from src.infrastructure.repositories import PostgresSettingsRepository
from src.infrastructure.verdict_pdf import build_questionnaire_verdict_pdf

router = APIRouter(tags=["questionnaires"])


def _stmt_by_id(questionnaire_id: UUID):
    return (
        select(QuestionnaireModel)
        .where(QuestionnaireModel.id == questionnaire_id)
        .options(
            selectinload(QuestionnaireModel.questions).selectinload(QuestionModel.options),
        )
    )


def questionnaire_to_public(row: QuestionnaireModel) -> QuestionnairePublic:
    questions_sorted = sorted(row.questions, key=lambda q: (q.order, str(q.id)))
    return QuestionnairePublic(
        id=row.id,
        title=row.title,
        llm_criteria=row.llm_criteria or "",
        created_at=row.created_at,
        updated_at=row.updated_at,
        questions=[
            QuestionPublic(
                id=q.id,
                text=q.text,
                type=q.type,
                order=q.order,
                min_score=q.min_score,
                max_score=q.max_score,
                options=[
                    QuestionOptionPublic(id=o.id, text=o.text, score=o.score)
                    for o in sorted(q.options, key=lambda x: (x.score, str(x.id)))
                ],
            )
            for q in questions_sorted
        ],
    )


async def _get_questionnaire_or_404(
    session: AsyncSessionDep,
    questionnaire_id: UUID,
) -> QuestionnaireModel:
    row = await session.scalar(_stmt_by_id(questionnaire_id))
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Опросник не найден")
    return row


async def _get_questionnaire_for_manage(
    session: AsyncSessionDep,
    questionnaire_id: UUID,
    user: PortalUserDep,
    organization_id: UUID | None,
) -> QuestionnaireModel:
    row = await session.scalar(_stmt_by_id(questionnaire_id))
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Опросник не найден")
    scope = resolve_organization_scope(user, organization_id)
    if user.role == ROLE_SUPER_ADMIN:
        if scope is None:
            if row.organization_id is not None:
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    detail="Опросник относится к организации — выберите контекст организации в панели",
                )
        elif row.organization_id != scope:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Нет доступа к этому опроснику")
    elif row.organization_id != scope:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Нет доступа к этому опроснику")
    return row


@router.get("/questionnaires", response_model=list[QuestionnaireListItem])
async def list_questionnaires(
    session: AsyncSessionDep,
    user: PortalUserDep,
    organization_id: UUID | None = Query(default=None, description="Только super_admin: фильтр по организации"),
) -> list[QuestionnaireListItem]:
    scope = resolve_organization_scope(user, organization_id)
    stmt = select(QuestionnaireModel).order_by(QuestionnaireModel.updated_at.desc())
    if user.role == ROLE_SUPER_ADMIN:
        if scope is None:
            stmt = stmt.where(QuestionnaireModel.organization_id.is_(None))
        else:
            stmt = stmt.where(QuestionnaireModel.organization_id == scope)
    else:
        stmt = stmt.where(QuestionnaireModel.organization_id == scope)
    r = await session.execute(stmt)
    rows = r.scalars().all()
    return [QuestionnaireListItem.model_validate(x) for x in rows]


@router.post("/questionnaires", response_model=QuestionnairePublic, status_code=status.HTTP_201_CREATED)
async def create_questionnaire(
    body: QuestionnaireCreate,
    session: AsyncSessionDep,
    user: PortalUserDep,
    organization_id: UUID | None = Query(default=None, description="Только super_admin: организация-владелец"),
) -> QuestionnairePublic:
    scope = resolve_organization_scope(user, organization_id)
    org_fk: UUID | None
    if user.role == ROLE_SUPER_ADMIN:
        org_fk = None if scope is None else scope
    else:
        org_fk = scope
    q_row = QuestionnaireModel(
        title=body.title.strip(),
        llm_criteria=(body.llm_criteria or "").strip(),
        organization_id=org_fk,
    )
    session.add(q_row)
    await session.flush()
    for qc in sorted(body.questions, key=lambda x: (x.order, x.text)):
        qm = QuestionModel(
            questionnaire_id=q_row.id,
            text=qc.text.strip(),
            type=qc.type,
            order=qc.order,
            min_score=qc.min_score,
            max_score=qc.max_score,
        )
        session.add(qm)
        await session.flush()
        for o in qc.options:
            session.add(
                QuestionOptionModel(
                    question_id=qm.id,
                    text=o.text.strip(),
                    score=o.score,
                )
            )
    await session.commit()
    loaded = await session.scalar(_stmt_by_id(q_row.id))
    assert loaded is not None
    return questionnaire_to_public(loaded)


@router.post("/questionnaires/verdict-pdf")
async def export_questionnaire_verdict_pdf(
    body: QuestionnaireVerdictPdfBody,
    settings: SettingsDep,
) -> Response:
    """Скачиваемый PDF с текстом вердикта ИИ (кириллица через DejaVu в Docker-образе)."""
    try:
        pdf_bytes, slug = build_questionnaire_verdict_pdf(
            title=body.title.strip(),
            analysis=body.analysis,
            tz=settings.app_zoneinfo,
        )
    except RuntimeError as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)) from e
    except Exception as e:
        logger.exception("verdict pdf build failed")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка формирования PDF: {e!s}",
        ) from e
    filename = f"{slug}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get("/questionnaires/{questionnaire_id}", response_model=QuestionnairePublic)
async def get_questionnaire(
    questionnaire_id: UUID,
    session: AsyncSessionDep,
) -> QuestionnairePublic:
    row = await _get_questionnaire_or_404(session, questionnaire_id)
    return questionnaire_to_public(row)


@router.put("/questionnaires/{questionnaire_id}", response_model=QuestionnairePublic)
async def update_questionnaire(
    questionnaire_id: UUID,
    body: QuestionnaireUpdate,
    session: AsyncSessionDep,
    user: PortalUserDep,
    organization_id: UUID | None = Query(default=None, description="Только super_admin: контекст организации"),
) -> QuestionnairePublic:
    row = await _get_questionnaire_for_manage(session, questionnaire_id, user, organization_id)
    row.title = body.title.strip()
    row.llm_criteria = (body.llm_criteria or "").strip()
    for qq in list(row.questions):
        await session.delete(qq)
    await session.flush()
    for qc in sorted(body.questions, key=lambda x: (x.order, x.text)):
        qm = QuestionModel(
            questionnaire_id=row.id,
            text=qc.text.strip(),
            type=qc.type,
            order=qc.order,
            min_score=qc.min_score,
            max_score=qc.max_score,
        )
        session.add(qm)
        await session.flush()
        for o in qc.options:
            session.add(
                QuestionOptionModel(
                    question_id=qm.id,
                    text=o.text.strip(),
                    score=o.score,
                )
            )
    await session.commit()
    loaded = await session.scalar(_stmt_by_id(questionnaire_id))
    assert loaded is not None
    return questionnaire_to_public(loaded)


@router.delete("/questionnaires/{questionnaire_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_questionnaire(
    questionnaire_id: UUID,
    session: AsyncSessionDep,
    user: PortalUserDep,
    organization_id: UUID | None = Query(default=None, description="Только super_admin: контекст организации"),
) -> Response:
    row = await _get_questionnaire_for_manage(session, questionnaire_id, user, organization_id)
    await session.delete(row)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _assert_option_score_in_range(q: QuestionModel, score: float) -> None:
    if not (q.min_score <= score <= q.max_score):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Балл варианта ({score}) вне допустимого диапазона вопроса "
                f"[{q.min_score}, {q.max_score}]"
            ),
        )


def _build_answers_for_llm(qn: QuestionnaireModel, body: AssessRequest) -> list[dict]:
    ordered = sorted(qn.questions, key=lambda x: (x.order, str(x.id)))
    if not ordered:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="В опроснике нет вопросов",
        )
    by_answer = {a.question_id: a for a in body.answers}
    if len(by_answer) != len(body.answers):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Дублируется question_id в ответах",
        )

    answers_for_llm: list[dict] = []

    for q in ordered:
        ans = by_answer.get(q.id)
        if ans is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=f"Нет ответа на вопрос: {q.text[:120]}",
            )
        opt_map = {o.id: o for o in q.options}

        if q.type == "single":
            if len(ans.option_ids) != 1:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail=f"Одиночный выбор: ожидается ровно один вариант (вопрос: {q.text[:80]})",
                )
            if ans.text_answer and ans.text_answer.strip():
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail="Для одиночного выбора не указывайте текстовый ответ",
                )
            oid = ans.option_ids[0]
            opt = opt_map.get(oid)
            if opt is None:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail="Выбран неизвестный вариант ответа",
                )
            _assert_option_score_in_range(q, opt.score)
            answers_for_llm.append(
                {
                    "question": q.text,
                    "type": q.type,
                    "selected_options": [{"text": opt.text, "score": opt.score}],
                    "aggregated_score": opt.score,
                    "question_score_range": {"min": q.min_score, "max": q.max_score},
                }
            )
        elif q.type == "multiple":
            if not ans.option_ids:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail=f"Множественный выбор: выберите хотя бы один вариант ({q.text[:80]})",
                )
            if ans.text_answer and ans.text_answer.strip():
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail="Для множественного выбора не указывайте текстовый ответ",
                )
            uniq = list(dict.fromkeys(ans.option_ids))
            if len(uniq) != len(ans.option_ids):
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail="Повтор вариантов в ответе",
                )
            selected = []
            total = 0.0
            for oid in uniq:
                opt = opt_map.get(oid)
                if opt is None:
                    raise HTTPException(
                        status.HTTP_400_BAD_REQUEST,
                        detail="Выбран неизвестный вариант ответа",
                    )
                _assert_option_score_in_range(q, opt.score)
                selected.append({"text": opt.text, "score": opt.score})
                total += opt.score
            answers_for_llm.append(
                {
                    "question": q.text,
                    "type": q.type,
                    "selected_options": selected,
                    "aggregated_score": total,
                    "question_score_range": {"min": q.min_score, "max": q.max_score},
                }
            )
        else:
            if ans.option_ids:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail="Текстовый вопрос: не передавайте option_ids",
                )
            text = (ans.text_answer or "").strip()
            if not text:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail=f"Введите текстовый ответ: {q.text[:80]}",
                )
            answers_for_llm.append(
                {
                    "question": q.text,
                    "type": q.type,
                    "text_answer": text,
                    "aggregated_score": None,
                    "question_score_range": {"min": q.min_score, "max": q.max_score},
                }
            )
    return answers_for_llm


async def _output_format_supplement_for_questionnaire(
    session: AsyncSession,
    redis: Redis,
    qn: QuestionnaireModel,
) -> str:
    repo = PostgresSettingsRepository(session, redis, organization_id=qn.organization_id)
    raw = await repo.get_value(sk.TEXT_BOT_SYSTEM_SUPPLEMENT)
    return (raw or "").strip()


@router.post("/questionnaires/{questionnaire_id}/assess", response_model=AssessResponse)
async def assess_questionnaire(
    questionnaire_id: UUID,
    body: AssessRequest,
    session: AsyncSessionDep,
    redis: RedisDep,
    llm: QuestionnaireLLMServiceDep,
) -> AssessResponse:
    qn = await _get_questionnaire_or_404(session, questionnaire_id)
    answers_for_llm = _build_answers_for_llm(qn, body)
    criteria = (qn.llm_criteria or "").strip()
    supplement = await _output_format_supplement_for_questionnaire(session, redis, qn)
    try:
        analysis = await llm.assess_answers(
            criteria=criteria,
            answers_for_llm=answers_for_llm,
            output_format_supplement=supplement,
        )
    except RuntimeError as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)) from e
    except Exception as e:
        logger.exception("questionnaire assess LLM failed")
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail=f"Ошибка LLM: {e!s}",
        ) from e

    return AssessResponse(analysis=analysis)


@router.post("/questionnaires/{questionnaire_id}/assess-stream")
async def assess_questionnaire_stream(
    questionnaire_id: UUID,
    body: AssessRequest,
    session: AsyncSessionDep,
    redis: RedisDep,
    llm: QuestionnaireLLMServiceDep,
) -> StreamingResponse:
    """Потоковая ИИ-оценка (SSE): фрагменты текста в событиях ``data: {"t":"..."}``; завершение — ``data: [DONE]``."""

    qn = await _get_questionnaire_or_404(session, questionnaire_id)
    answers_for_llm = _build_answers_for_llm(qn, body)
    criteria = (qn.llm_criteria or "").strip()
    supplement = await _output_format_supplement_for_questionnaire(session, redis, qn)

    async def gen():
        try:
            async for piece in llm.assess_answers_stream(
                criteria=criteria,
                answers_for_llm=answers_for_llm,
                output_format_supplement=supplement,
            ):
                yield f"data: {json.dumps({'t': piece}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except RuntimeError as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.exception("questionnaire assess stream LLM failed")
            yield f"data: {json.dumps({'error': f'Ошибка LLM: {e!s}'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
