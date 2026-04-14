"""Конструктор форм: шаблоны, мероприятия, ответы, публичная отправка, экспорт XLSX."""

from __future__ import annotations

import logging
from datetime import date, datetime, time
from io import BytesIO
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from openpyxl import Workbook
from sqlalchemy import delete, func, select
from sqlalchemy.orm import selectinload
from starlette.responses import Response

from src.api.dependencies import (
    AsyncSessionDep,
    MaxMessengerClientDep,
    SettingsDep,
    SettingsRepositoryDep,
)
from src.infrastructure.services.shop_order_notify import (
    resolve_telegram_bot_token,
    send_max_order_message,
    send_telegram_order_message,
    send_vk_order_message,
)
from src.api.schemas.registration_forms import (
    FormFieldSchema,
    FormTemplateCreate,
    FormTemplateResponse,
    FormTemplateUpdate,
    PublicRegistrationPayload,
    PublicRegistrationSubmitBody,
    RegistrationEventCreate,
    RegistrationEventDetail,
    RegistrationEventListItem,
    RegistrationEventUpdate,
    RegistrationSubmissionItem,
)
from src.core.config import Settings
from src.infrastructure.models import (
    FormTemplateModel,
    RegistrationEventModel,
    RegistrationEventScheduleModel,
    RegistrationSubmissionModel,
    ScheduleModel,
)

router = APIRouter(prefix="/forms", tags=["registration-forms"])

logger = logging.getLogger(__name__)

CLOSED_MSG = "Регистрация завершена."


def _deadline_end_of_day(end_day: date, settings: Settings) -> datetime:
    return datetime.combine(end_day, time(23, 59, 59), tzinfo=settings.app_zoneinfo)


def _now(settings: Settings) -> datetime:
    return datetime.now(settings.app_zoneinfo)


def _registration_open(ev: RegistrationEventModel, settings: Settings) -> bool:
    if ev.registration_closed_early:
        return False
    return _now(settings) <= ev.registration_deadline_at


def _fields_from_model(row: FormTemplateModel) -> list[FormFieldSchema]:
    raw = row.fields or []
    if not isinstance(raw, list):
        return []
    return [FormFieldSchema.model_validate(x) for x in raw]


def _template_to_response(row: FormTemplateModel) -> FormTemplateResponse:
    return FormTemplateResponse(
        id=row.id,
        name=row.name,
        description=row.description or "",
        fields=_fields_from_model(row),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def _submission_counts(session: AsyncSessionDep) -> dict[UUID, int]:
    r = await session.execute(
        select(RegistrationSubmissionModel.event_id, func.count(RegistrationSubmissionModel.id)).group_by(
            RegistrationSubmissionModel.event_id,
        ),
    )
    return {eid: int(c) for eid, c in r.all()}


async def _schedule_ids_for_event(session: AsyncSessionDep, event_id: UUID) -> list[UUID]:
    r = await session.execute(
        select(RegistrationEventScheduleModel.schedule_id).where(RegistrationEventScheduleModel.event_id == event_id),
    )
    return [row[0] for row in r.all()]


async def _set_event_schedules(session: AsyncSessionDep, event_id: UUID, schedule_ids: list[UUID]) -> None:
    await session.execute(delete(RegistrationEventScheduleModel).where(RegistrationEventScheduleModel.event_id == event_id))
    for sid in schedule_ids:
        session.add(RegistrationEventScheduleModel(event_id=event_id, schedule_id=sid))


async def _verify_schedule_ids(session: AsyncSessionDep, schedule_ids: list[UUID]) -> None:
    if not schedule_ids:
        return
    r = await session.execute(select(ScheduleModel.id).where(ScheduleModel.id.in_(schedule_ids)))
    found = {row[0] for row in r.all()}
    missing = set(schedule_ids) - found
    if missing:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"Расписания не найдены: {', '.join(str(x) for x in missing)}",
        )


def _validate_and_normalize_answers(fields: list[FormFieldSchema], answers: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for f in sorted(fields, key=lambda x: (x.order, x.id)):
        raw = answers.get(f.id)
        if f.required:
            if raw is None:
                raise ValueError(f"Заполните обязательное поле: {f.label}")
            if isinstance(raw, str) and not raw.strip():
                raise ValueError(f"Заполните обязательное поле: {f.label}")
            if f.type == "multiple_choice":
                if not isinstance(raw, list) or len(raw) == 0:
                    raise ValueError(f"Заполните обязательное поле: {f.label}")

        if raw is None or raw == "":
            continue

        if f.type in ("short_text", "long_text", "phone", "email"):
            s = str(raw).strip()
            if not s and f.required:
                raise ValueError(f"Заполните поле: {f.label}")
            if s:
                out[f.id] = s
            continue

        if f.type == "number":
            try:
                if isinstance(raw, bool):
                    raise ValueError
                if isinstance(raw, (int, float)):
                    out[f.id] = raw
                else:
                    s = str(raw).strip().replace(",", ".")
                    if "." in s:
                        out[f.id] = float(s)
                    else:
                        out[f.id] = int(s)
            except (TypeError, ValueError):
                raise ValueError(f"Поле «{f.label}»: ожидается число") from None
            continue

        if f.type == "date":
            s = str(raw).strip()
            try:
                date.fromisoformat(s)
            except ValueError:
                raise ValueError(f"Поле «{f.label}»: ожидается дата YYYY-MM-DD") from None
            out[f.id] = s
            continue

        if f.type == "single_choice":
            s = str(raw).strip()
            if s not in f.options:
                raise ValueError(f"Поле «{f.label}»: недопустимый вариант")
            out[f.id] = s
            continue

        if f.type == "multiple_choice":
            if not isinstance(raw, list):
                raw = [raw]
            chosen: list[str] = []
            for item in raw:
                t = str(item).strip()
                if t and t not in chosen:
                    if t not in f.options:
                        raise ValueError(f"Поле «{f.label}»: недопустимый вариант «{t}»")
                    chosen.append(t)
            if chosen:
                out[f.id] = chosen

    for f in fields:
        if not f.required:
            continue
        if f.id not in out:
            raise ValueError(f"Заполните обязательное поле: {f.label}")
    return out


def _answers_human_lines(fields: list[FormFieldSchema], answers: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for f in sorted(fields, key=lambda x: (x.order, x.id)):
        v = answers.get(f.id)
        if v is None:
            continue
        if isinstance(v, list):
            lines.append(f"{f.label}: {', '.join(str(x) for x in v)}")
        else:
            lines.append(f"{f.label}: {v}")
    return lines


def _format_registration_notify_text(
    event_title: str,
    event_subtitle: str,
    fields: list[FormFieldSchema],
    answers: dict[str, Any],
    total_registered: int,
) -> str:
    detail_lines = _answers_human_lines(fields, answers)
    body = "\n".join(detail_lines) if detail_lines else "(поля не заполнены)"
    sub = (event_subtitle or "").strip()
    head = f"Новая регистрация: {event_title}"
    if sub:
        head = f"{head}\n{sub}"
    return (
        f"{head}\n"
        f"---\n"
        f"{body}\n"
        f"---\n"
        f"Всего зарегистрировано: {total_registered}"
    )


async def _notify_registration_optional(
    ev: RegistrationEventModel,
    fields: list[FormFieldSchema],
    answers: dict[str, Any],
    total_registered: int,
    *,
    settings: Settings,
    settings_repo: Any,
    max_client: Any,
) -> None:
    m = (ev.notify_messenger or "").strip().lower()
    chat = (ev.notify_chat_id or "").strip()
    if not m or not chat:
        return
    text = _format_registration_notify_text(ev.title, ev.title_subtitle or "", fields, answers, total_registered)
    try:
        if m == "max":
            cid = int(chat, 10)
            if not (await max_client.resolve_bot_token()).strip():
                logger.warning("registration notify: нет MAX_BOT_TOKEN, event_id=%s", ev.id)
                return
            await send_max_order_message(max_client, cid, text)
        elif m == "telegram":
            tok = (await resolve_telegram_bot_token(settings_repo, settings)).strip()
            if not tok:
                logger.warning("registration notify: нет TELEGRAM_BOT_TOKEN, event_id=%s", ev.id)
                return
            await send_telegram_order_message(tok, chat, text)
        elif m == "vk":
            peer = int(chat, 10)
            tok = (settings.vk_api_access_token or "").strip()
            if not tok:
                logger.warning("registration notify: нет VK_API_ACCESS_TOKEN, event_id=%s", ev.id)
                return
            await send_vk_order_message(tok, peer, text)
    except Exception:
        logger.exception(
            "registration notify: сбой отправки (messenger=%s), event_id=%s",
            m,
            ev.id,
        )


def _normalize_event_notify_pair(ev: RegistrationEventModel) -> None:
    """Убрать неполную пару мессенджер / чат."""
    m = (ev.notify_messenger or "").strip().lower() or None
    c = (ev.notify_chat_id or "").strip() or None
    if m and not c:
        ev.notify_messenger = None
        ev.notify_chat_id = None
    elif c and not m:
        ev.notify_messenger = None
        ev.notify_chat_id = None
    else:
        ev.notify_messenger = m
        ev.notify_chat_id = c


def _event_to_list_item(
    ev: RegistrationEventModel,
    template_name: str,
    counts: dict[UUID, int],
    schedule_ids: list[UUID],
    settings: Settings,
) -> RegistrationEventListItem:
    open_ = _registration_open(ev, settings)
    return RegistrationEventListItem(
        id=ev.id,
        title=ev.title,
        title_subtitle=ev.title_subtitle or "",
        form_template_id=ev.form_template_id,
        form_template_name=template_name,
        event_start_date=ev.event_start_date,
        event_end_date=ev.event_end_date,
        registration_deadline_at=ev.registration_deadline_at,
        registration_closed_early=ev.registration_closed_early,
        registration_open=open_,
        submissions_count=counts.get(ev.id, 0),
        schedule_ids=schedule_ids,
        notify_messenger=ev.notify_messenger,
        notify_chat_id=ev.notify_chat_id,
        created_at=ev.created_at,
        updated_at=ev.updated_at,
    )


async def _get_event_loaded(session: AsyncSessionDep, event_id: UUID) -> RegistrationEventModel | None:
    return await session.scalar(
        select(RegistrationEventModel)
        .where(RegistrationEventModel.id == event_id)
        .options(selectinload(RegistrationEventModel.form_template)),
    )


# --- Шаблоны форм ---


@router.get("/templates", response_model=list[FormTemplateResponse])
async def list_form_templates(session: AsyncSessionDep) -> list[FormTemplateResponse]:
    r = await session.execute(select(FormTemplateModel).order_by(FormTemplateModel.updated_at.desc()))
    rows = r.scalars().all()
    return [_template_to_response(x) for x in rows]


@router.post("/templates", response_model=FormTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_form_template(body: FormTemplateCreate, session: AsyncSessionDep) -> FormTemplateResponse:
    fields_json = [f.model_dump() for f in body.fields]
    row = FormTemplateModel(
        name=body.name.strip(),
        description=(body.description or "").strip(),
        fields=fields_json,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _template_to_response(row)


@router.get("/templates/{template_id}", response_model=FormTemplateResponse)
async def get_form_template(template_id: UUID, session: AsyncSessionDep) -> FormTemplateResponse:
    row = await session.get(FormTemplateModel, template_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Шаблон не найден")
    return _template_to_response(row)


@router.patch("/templates/{template_id}", response_model=FormTemplateResponse)
async def patch_form_template(
    template_id: UUID,
    body: FormTemplateUpdate,
    session: AsyncSessionDep,
) -> FormTemplateResponse:
    row = await session.get(FormTemplateModel, template_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Шаблон не найден")
    if body.name is not None:
        row.name = body.name.strip()
    if body.description is not None:
        row.description = body.description.strip()
    if body.fields is not None:
        row.fields = [f.model_dump() for f in body.fields]
    await session.commit()
    await session.refresh(row)
    return _template_to_response(row)


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_form_template(template_id: UUID, session: AsyncSessionDep) -> Response:
    cnt = await session.scalar(
        select(func.count()).select_from(RegistrationEventModel).where(RegistrationEventModel.form_template_id == template_id),
    )
    if cnt and int(cnt) > 0:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Нельзя удалить шаблон: есть мероприятия с этой формой",
        )
    row = await session.get(FormTemplateModel, template_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Шаблон не найден")
    await session.delete(row)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Мероприятия ---


@router.get("/events", response_model=list[RegistrationEventListItem])
async def list_registration_events(session: AsyncSessionDep, settings: SettingsDep) -> list[RegistrationEventListItem]:
    counts = await _submission_counts(session)
    r = await session.execute(
        select(RegistrationEventModel, FormTemplateModel.name)
        .join(FormTemplateModel, FormTemplateModel.id == RegistrationEventModel.form_template_id)
        .order_by(RegistrationEventModel.created_at.desc()),
    )
    out: list[RegistrationEventListItem] = []
    for ev, tmpl_name in r.all():
        sids = await _schedule_ids_for_event(session, ev.id)
        out.append(_event_to_list_item(ev, tmpl_name, counts, sids, settings))
    return out


@router.post("/events", response_model=RegistrationEventDetail, status_code=status.HTTP_201_CREATED)
async def create_registration_event(
    body: RegistrationEventCreate,
    session: AsyncSessionDep,
    settings: SettingsDep,
) -> RegistrationEventDetail:
    tmpl = await session.get(FormTemplateModel, body.form_template_id)
    if tmpl is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Шаблон формы не найден")
    await _verify_schedule_ids(session, body.schedule_ids)
    deadline = body.registration_deadline_at or _deadline_end_of_day(body.event_end_date, settings)
    ev = RegistrationEventModel(
        title=body.title.strip(),
        title_subtitle=(body.title_subtitle or "").strip(),
        form_template_id=body.form_template_id,
        event_start_date=body.event_start_date,
        event_end_date=body.event_end_date,
        registration_deadline_at=deadline,
        registration_closed_early=False,
        notify_messenger=body.notify_messenger,
        notify_chat_id=(body.notify_chat_id or "").strip() or None,
    )
    _normalize_event_notify_pair(ev)
    session.add(ev)
    await session.flush()
    await _set_event_schedules(session, ev.id, body.schedule_ids)
    await session.commit()
    await session.refresh(ev)
    counts = await _submission_counts(session)
    sids = await _schedule_ids_for_event(session, ev.id)
    return RegistrationEventDetail.model_validate(
        _event_to_list_item(ev, tmpl.name, counts, sids, settings).model_dump(),
    )


@router.get("/events/{event_id}", response_model=RegistrationEventDetail)
async def get_registration_event(event_id: UUID, session: AsyncSessionDep, settings: SettingsDep) -> RegistrationEventDetail:
    ev = await _get_event_loaded(session, event_id)
    if ev is None or ev.form_template is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Мероприятие не найдено")
    counts = await _submission_counts(session)
    sids = await _schedule_ids_for_event(session, ev.id)
    return RegistrationEventDetail.model_validate(
        _event_to_list_item(ev, ev.form_template.name, counts, sids, settings).model_dump(),
    )


@router.patch("/events/{event_id}", response_model=RegistrationEventDetail)
async def patch_registration_event(
    event_id: UUID,
    body: RegistrationEventUpdate,
    session: AsyncSessionDep,
    settings: SettingsDep,
) -> RegistrationEventDetail:
    ev = await _get_event_loaded(session, event_id)
    if ev is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Мероприятие не найдено")
    if body.form_template_id is not None:
        tmpl = await session.get(FormTemplateModel, body.form_template_id)
        if tmpl is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Шаблон формы не найден")
        ev.form_template_id = body.form_template_id
    if body.title is not None:
        ev.title = body.title.strip()
    if "title_subtitle" in body.model_fields_set:
        ev.title_subtitle = (body.title_subtitle or "").strip()
    if body.event_start_date is not None:
        ev.event_start_date = body.event_start_date
    if body.event_end_date is not None:
        ev.event_end_date = body.event_end_date
    if body.event_start_date is not None or body.event_end_date is not None:
        if ev.event_end_date < ev.event_start_date:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Дата окончания раньше даты начала")
    if body.registration_deadline_at is not None:
        ev.registration_deadline_at = body.registration_deadline_at
    if body.registration_closed_early is not None:
        ev.registration_closed_early = body.registration_closed_early
    if body.schedule_ids is not None:
        await _verify_schedule_ids(session, body.schedule_ids)
        await _set_event_schedules(session, ev.id, body.schedule_ids)
    if "notify_messenger" in body.model_fields_set:
        ev.notify_messenger = body.notify_messenger
    if "notify_chat_id" in body.model_fields_set:
        ev.notify_chat_id = (body.notify_chat_id or "").strip() or None
    _normalize_event_notify_pair(ev)
    await session.commit()
    await session.refresh(ev)
    ev2 = await _get_event_loaded(session, event_id)
    assert ev2 is not None and ev2.form_template is not None
    counts = await _submission_counts(session)
    sids = await _schedule_ids_for_event(session, ev2.id)
    return RegistrationEventDetail.model_validate(
        _event_to_list_item(ev2, ev2.form_template.name, counts, sids, settings).model_dump(),
    )


@router.delete("/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_registration_event(event_id: UUID, session: AsyncSessionDep) -> Response:
    ev = await session.get(RegistrationEventModel, event_id)
    if ev is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Мероприятие не найдено")
    await session.delete(ev)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/events/{event_id}/submissions", response_model=list[RegistrationSubmissionItem])
async def list_submissions(event_id: UUID, session: AsyncSessionDep) -> list[RegistrationSubmissionItem]:
    ev = await session.get(RegistrationEventModel, event_id)
    if ev is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Мероприятие не найдено")
    r = await session.execute(
        select(RegistrationSubmissionModel)
        .where(RegistrationSubmissionModel.event_id == event_id)
        .order_by(RegistrationSubmissionModel.submitted_at.desc()),
    )
    rows = r.scalars().all()
    return [
        RegistrationSubmissionItem(
            id=x.id,
            event_id=x.event_id,
            answers=dict(x.answers or {}),
            submitted_at=x.submitted_at,
        )
        for x in rows
    ]


@router.delete(
    "/events/{event_id}/submissions/{submission_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_submission(
    event_id: UUID,
    submission_id: UUID,
    session: AsyncSessionDep,
) -> Response:
    sub = await session.get(RegistrationSubmissionModel, submission_id)
    if sub is None or sub.event_id != event_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Заявка не найдена")
    await session.delete(sub)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/events/{event_id}/export.xlsx")
async def export_submissions_xlsx(event_id: UUID, session: AsyncSessionDep) -> Response:
    ev = await _get_event_loaded(session, event_id)
    if ev is None or ev.form_template is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Мероприятие не найдено")
    fields = _fields_from_model(ev.form_template)
    labels = [f.label for f in sorted(fields, key=lambda x: (x.order, x.id))]
    field_ids = [f.id for f in sorted(fields, key=lambda x: (x.order, x.id))]

    r = await session.execute(
        select(RegistrationSubmissionModel)
        .where(RegistrationSubmissionModel.event_id == event_id)
        .order_by(RegistrationSubmissionModel.submitted_at.asc()),
    )
    subs = r.scalars().all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Ответы"
    header = ["id", "submitted_at", *labels]
    ws.append(header)
    for s in subs:
        row: list[Any] = [str(s.id), s.submitted_at.isoformat()]
        ans = dict(s.answers or {})
        for fid in field_ids:
            v = ans.get(fid)
            if isinstance(v, list):
                row.append("; ".join(str(x) for x in v))
            elif v is None:
                row.append("")
            else:
                row.append(str(v))
        ws.append(row)

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    fname = f"registration_{event_id}.xlsx"
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


# --- Публично (без JWT) ---


@router.get("/public/events/{event_id}", response_model=PublicRegistrationPayload)
async def public_event_form(event_id: UUID, session: AsyncSessionDep, settings: SettingsDep) -> PublicRegistrationPayload:
    ev = await _get_event_loaded(session, event_id)
    if ev is None or ev.form_template is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Мероприятие не найдено")
    open_ = _registration_open(ev, settings)
    fields = _fields_from_model(ev.form_template) if open_ else []
    return PublicRegistrationPayload(
        event_id=ev.id,
        event_title=ev.title,
        event_subtitle=ev.title_subtitle or "",
        event_start_date=ev.event_start_date,
        event_end_date=ev.event_end_date,
        registration_open=open_,
        closed_message=CLOSED_MSG,
        fields=fields,
    )


@router.post("/public/events/{event_id}/submit", status_code=status.HTTP_201_CREATED)
async def public_submit_form(
    event_id: UUID,
    body: PublicRegistrationSubmitBody,
    session: AsyncSessionDep,
    settings: SettingsDep,
    settings_repo: SettingsRepositoryDep,
    max_client: MaxMessengerClientDep,
) -> dict[str, str]:
    ev = await _get_event_loaded(session, event_id)
    if ev is None or ev.form_template is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Мероприятие не найдено")
    if not _registration_open(ev, settings):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=CLOSED_MSG)
    fields = _fields_from_model(ev.form_template)
    try:
        normalized = _validate_and_normalize_answers(fields, body.answers)
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e
    sub = RegistrationSubmissionModel(event_id=ev.id, answers=normalized)
    session.add(sub)
    await session.commit()
    total_q = await session.scalar(
        select(func.count())
        .select_from(RegistrationSubmissionModel)
        .where(RegistrationSubmissionModel.event_id == ev.id),
    )
    total_registered = int(total_q or 0)
    await _notify_registration_optional(
        ev,
        fields,
        normalized,
        total_registered,
        settings=settings,
        settings_repo=settings_repo,
        max_client=max_client,
    )
    return {"status": "ok"}
