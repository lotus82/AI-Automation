"""CRUD расписаний и загрузка событий (DATABASE / REMINDER)."""

from __future__ import annotations

import csv
import json
import logging
from dataclasses import replace
from datetime import datetime
from io import StringIO
from typing import Any
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from starlette.responses import Response

from src.api.dependencies import AsyncSessionDep
from src.core.config import get_settings
from src.api.schemas.schedules import (
    ScheduleCreateBody,
    ScheduleEventsUploadResult,
    SchedulePatchBody,
    ScheduleResponse,
)
from src.domain.entities import Schedule, ScheduledEvent
from src.infrastructure.repositories import SqlAlchemyScheduleRepository

logger = logging.getLogger(__name__)

router = APIRouter(tags=["schedules"])

_MAX_UPLOAD_BYTES = 5 * 1024 * 1024


def _parse_datetime_value(raw: str) -> datetime:
    s = (raw or "").strip()
    if not s:
        msg = "Пустая дата/время"
        raise ValueError(msg)
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        # Без смещения в файле трактуем как локальное время офиса (APP_TIMEZONE), не UTC.
        dt = dt.replace(tzinfo=get_settings().app_zoneinfo)
    return dt


def _normalize_csv_row(row: dict[str, Any]) -> dict[str, str]:
    return {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}


def _rows_from_json_payload(data: Any) -> list[tuple[datetime, dict[str, Any]]]:
    if not isinstance(data, list):
        msg = "JSON: ожидается массив объектов"
        raise ValueError(msg)
    out: list[tuple[datetime, dict[str, Any]]] = []
    for i, row in enumerate(data):
        if not isinstance(row, dict):
            msg = f"Строка {i + 1}: ожидался объект"
            raise ValueError(msg)
        raw_dt = row.get("event_datetime") or row.get("datetime")
        if raw_dt is None:
            msg = f"Строка {i + 1}: нет поля event_datetime"
            raise ValueError(msg)
        dt = _parse_datetime_value(str(raw_dt))
        ed_raw = row.get("event_data")
        if ed_raw is not None:
            if not isinstance(ed_raw, dict):
                msg = f"Строка {i + 1}: event_data должен быть объектом"
                raise ValueError(msg)
            ev_data = dict(ed_raw)
        else:
            skip = {"event_datetime", "datetime"}
            ev_data = {str(k): v for k, v in row.items() if k not in skip and v is not None}
        out.append((dt, ev_data))
    return out


def _rows_from_csv_text(text: str) -> list[tuple[datetime, dict[str, Any]]]:
    reader = csv.DictReader(StringIO(text))
    if not reader.fieldnames:
        msg = "CSV: нет заголовка"
        raise ValueError(msg)
    fields_lower = {(f or "").strip().lower() for f in reader.fieldnames}
    if "event_datetime" not in fields_lower:
        msg = "CSV: нужна колонка event_datetime"
        raise ValueError(msg)
    out: list[tuple[datetime, dict[str, Any]]] = []
    for row in reader:
        rd = _normalize_csv_row(row)
        dt_s = rd.get("event_datetime", "")
        if not dt_s:
            continue
        dt = _parse_datetime_value(dt_s)
        ev_data = {k: v for k, v in rd.items() if k != "event_datetime" and v != ""}
        out.append((dt, ev_data))
    if not out:
        msg = "CSV: нет ни одной строки с event_datetime"
        raise ValueError(msg)
    return out


def _merge_schedule_patch(existing: Schedule, patch: SchedulePatchBody) -> Schedule:
    """Накладывает только явно заданные в PATCH поля (model_fields_set)."""
    fs = patch.model_fields_set
    kwargs: dict[str, Any] = {}
    if "chat_id" in fs:
        kwargs["chat_id"] = (patch.chat_id or "").strip()
    if "is_active" in fs:
        kwargs["is_active"] = bool(patch.is_active)
    if "type" in fs and patch.type is not None:
        kwargs["type"] = patch.type
    if "prompt" in fs:
        kwargs["prompt"] = patch.prompt if patch.prompt is not None else ""
    if "content_template" in fs:
        kwargs["content_template"] = (
            patch.content_template if patch.content_template is not None else ""
        )
    if "interval_settings" in fs:
        kwargs["interval_settings"] = dict(patch.interval_settings or {})
    if "reminder_offset_minutes" in fs:
        kwargs["reminder_offset_minutes"] = patch.reminder_offset_minutes
    return replace(existing, **kwargs)


def _schedule_to_response(s: Schedule) -> ScheduleResponse:
    if s.id is None:
        msg = "Внутренняя ошибка: расписание без id"
        raise ValueError(msg)
    return ScheduleResponse(
        id=s.id,
        chat_id=s.chat_id,
        is_active=s.is_active,
        type=s.type,
        prompt=s.prompt,
        content_template=s.content_template,
        interval_settings=dict(s.interval_settings or {}),
        reminder_offset_minutes=s.reminder_offset_minutes,
        last_run_at=s.last_run_at,
        created_at=s.created_at,
    )


@router.get(
    "/schedules",
    response_model=list[ScheduleResponse],
    summary="Список расписаний",
)
async def list_schedules(session: AsyncSessionDep) -> list[ScheduleResponse]:
    repo = SqlAlchemyScheduleRepository(session)
    rows = await repo.list_schedules(active_only=False)
    return [_schedule_to_response(s) for s in rows]


@router.get(
    "/schedules/{schedule_id}",
    response_model=ScheduleResponse,
    summary="Одно расписание по id",
)
async def get_schedule(
    schedule_id: UUID,
    session: AsyncSessionDep,
) -> ScheduleResponse:
    repo = SqlAlchemyScheduleRepository(session)
    row = await repo.get_by_id(schedule_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Расписание не найдено")
    return _schedule_to_response(row)


@router.patch(
    "/schedules/{schedule_id}",
    response_model=ScheduleResponse,
    summary="Обновить расписание (частично)",
)
async def patch_schedule(
    schedule_id: UUID,
    body: SchedulePatchBody,
    session: AsyncSessionDep,
) -> ScheduleResponse:
    repo = SqlAlchemyScheduleRepository(session)
    existing = await repo.get_by_id(schedule_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Расписание не найдено")
    if not body.model_fields_set:
        raise HTTPException(status_code=400, detail="Нет полей для обновления")
    merged = _merge_schedule_patch(existing, body)
    saved = await repo.update(merged)
    if saved is None:
        raise HTTPException(status_code=404, detail="Расписание не найдено")
    await session.commit()
    return _schedule_to_response(saved)


@router.post(
    "/schedules",
    response_model=ScheduleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать расписание",
)
async def create_schedule(
    body: ScheduleCreateBody,
    session: AsyncSessionDep,
) -> ScheduleResponse:
    repo = SqlAlchemyScheduleRepository(session)
    entity = Schedule(
        chat_id=body.chat_id.strip(),
        is_active=body.is_active,
        type=body.type,
        prompt=body.prompt,
        content_template=body.content_template,
        interval_settings=dict(body.interval_settings or {}),
        reminder_offset_minutes=body.reminder_offset_minutes,
    )
    saved = await repo.create(entity)
    await session.commit()
    if saved.id is None:
        raise HTTPException(status_code=500, detail="Не удалось создать расписание")
    return _schedule_to_response(saved)


@router.delete(
    "/schedules/{schedule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Удалить расписание",
)
async def delete_schedule(
    schedule_id: UUID,
    session: AsyncSessionDep,
) -> Response:
    """204 без тела: иначе FastAPI пытается отдать JSON и падает на assert."""
    repo = SqlAlchemyScheduleRepository(session)
    ok = await repo.delete(schedule_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Расписание не найдено")
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/schedules/{schedule_id}/upload-events",
    response_model=ScheduleEventsUploadResult,
    summary="Загрузить события (CSV или JSON)",
)
async def upload_schedule_events(
    schedule_id: UUID,
    session: AsyncSessionDep,
    file: UploadFile = File(..., description="Файл .csv или .json"),
) -> ScheduleEventsUploadResult:
    repo = SqlAlchemyScheduleRepository(session)
    sch = await repo.get_by_id(schedule_id)
    if sch is None:
        raise HTTPException(status_code=404, detail="Расписание не найдено")

    raw = await file.read()
    if len(raw) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Файл слишком большой (макс. 5 МБ)")
    name = (file.filename or "").lower()
    errors: list[str] = []
    pairs: list[tuple[datetime, dict[str, Any]]] = []
    try:
        if name.endswith(".json") or raw.strip().startswith(b"["):
            data = json.loads(raw.decode("utf-8-sig"))
            pairs = _rows_from_json_payload(data)
        elif name.endswith(".csv") or b"," in raw[:200]:
            text = raw.decode("utf-8-sig")
            pairs = _rows_from_csv_text(text)
        else:
            raise HTTPException(
                status_code=400,
                detail="Поддерживаются файлы .csv и .json",
            )
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Некорректный JSON: {e}") from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    events: list[ScheduledEvent] = []
    for dt, ev_data in pairs:
        events.append(
            ScheduledEvent(
                schedule_id=schedule_id,
                event_datetime=dt,
                event_data=ev_data,
            ),
        )

    try:
        n = await repo.add_events_bulk(schedule_id, events)
        await session.commit()
    except Exception:
        await session.rollback()
        logger.exception("Импорт событий расписания: ошибка БД schedule_id=%s", schedule_id)
        raise HTTPException(status_code=500, detail="Ошибка записи в базу") from None

    return ScheduleEventsUploadResult(imported=n, errors=errors)
