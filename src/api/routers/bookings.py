"""Онлайн-запись к сотрудникам: настройки, блокировки, записи, публичные слоты."""

from __future__ import annotations

import logging
from collections import Counter
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from src.api.dependencies import AsyncSessionDep, SettingsDep
from src.api.dependencies_portal import PortalUserDep
from src.api.org_scope import resolve_organization_scope
from src.api.schemas.bookings import (
    AppointmentOut,
    BookingConfigOut,
    BookingConfigUpsert,
    BookingStatsOut,
    BusySlotCreate,
    BusySlotOut,
    PublicAppointmentCreate,
    PublicSlotItem,
    PublicSlotsOut,
)
from src.core.config import Settings
from src.infrastructure.models import AppointmentModel, BookingConfigModel, BusySlotModel, PortalUserModel
from src.infrastructure.services.booking_service import compute_available_slots

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bookings", tags=["bookings"])
public_router = APIRouter(prefix="/public/bookings", tags=["bookings-public"])

_UTC = ZoneInfo("UTC")


def _org_id(user: PortalUserModel, organization_id: UUID | None) -> UUID:
    oid = resolve_organization_scope(user, organization_id)
    if oid is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Укажите organization_id (контекст организации)",
        )
    return oid


def _day_bounds_utc(d: date, settings: Settings) -> tuple[datetime, datetime]:
    tz = settings.app_zoneinfo
    start = datetime.combine(d, time(0, 0), tzinfo=tz)
    end = start + timedelta(days=1)
    return start.astimezone(_UTC), end.astimezone(_UTC)


def _busy_intervals(rows: list[BusySlotModel]) -> list[tuple[datetime, datetime]]:
    return [(b.start_time, b.end_time) for b in rows]


def _appointment_blocking_intervals(rows: list[AppointmentModel]) -> list[tuple[datetime, datetime]]:
    return [(a.start_time, a.end_time) for a in rows if a.status not in ("canceled",)]


@router.get("/config", response_model=BookingConfigOut)
async def get_booking_config(
    user: PortalUserDep,
    session: AsyncSessionDep,
    organization_id: UUID | None = Query(None),
) -> BookingConfigOut:
    oid = _org_id(user, organization_id)
    stmt = select(BookingConfigModel).where(
        BookingConfigModel.portal_user_id == user.id,
        BookingConfigModel.organization_id == oid,
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        return BookingConfigOut(working_hours={}, appointment_duration=30)
    return BookingConfigOut(
        id=row.id,
        working_hours=dict(row.working_hours or {}),
        appointment_duration=int(row.appointment_duration),
    )


@router.put("/config", response_model=BookingConfigOut)
async def put_booking_config(
    body: BookingConfigUpsert,
    user: PortalUserDep,
    session: AsyncSessionDep,
    organization_id: UUID | None = Query(None),
) -> BookingConfigOut:
    oid = _org_id(user, organization_id)
    stmt = select(BookingConfigModel).where(
        BookingConfigModel.portal_user_id == user.id,
        BookingConfigModel.organization_id == oid,
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        row = BookingConfigModel(
            portal_user_id=user.id,
            organization_id=oid,
            working_hours=body.working_hours,
            appointment_duration=body.appointment_duration,
        )
        session.add(row)
    else:
        row.working_hours = body.working_hours
        row.appointment_duration = body.appointment_duration
    await session.commit()
    await session.refresh(row)
    return BookingConfigOut(
        id=row.id,
        working_hours=dict(row.working_hours or {}),
        appointment_duration=int(row.appointment_duration),
    )


@router.get("/busy-slots", response_model=list[BusySlotOut])
async def list_busy_slots(
    user: PortalUserDep,
    session: AsyncSessionDep,
    settings: SettingsDep,
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
) -> list[BusySlotOut]:
    stmt = select(BusySlotModel).where(BusySlotModel.portal_user_id == user.id)
    if from_date is not None:
        u0, _ = _day_bounds_utc(from_date, settings)
        stmt = stmt.where(BusySlotModel.end_time >= u0)
    if to_date is not None:
        _, u1 = _day_bounds_utc(to_date, settings)
        stmt = stmt.where(BusySlotModel.start_time < u1)
    stmt = stmt.order_by(BusySlotModel.start_time.asc())
    rows = (await session.execute(stmt)).scalars().all()
    return [
        BusySlotOut(
            id=r.id,
            start_time=r.start_time,
            end_time=r.end_time,
            reason=(r.reason or ""),
        )
        for r in rows
    ]


@router.post("/busy-slots", response_model=BusySlotOut, status_code=status.HTTP_201_CREATED)
async def create_busy_slot(
    body: BusySlotCreate,
    user: PortalUserDep,
    session: AsyncSessionDep,
) -> BusySlotOut:
    if body.end_time <= body.start_time:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="end_time должен быть позже start_time")
    row = BusySlotModel(
        portal_user_id=user.id,
        start_time=body.start_time,
        end_time=body.end_time,
        reason=(body.reason or "")[:512],
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return BusySlotOut(
        id=row.id,
        start_time=row.start_time,
        end_time=row.end_time,
        reason=row.reason or "",
    )


@router.delete("/busy-slots/{slot_id}", response_class=Response)
async def delete_busy_slot(
    slot_id: UUID,
    user: PortalUserDep,
    session: AsyncSessionDep,
) -> Response:
    stmt = select(BusySlotModel).where(
        BusySlotModel.id == slot_id,
        BusySlotModel.portal_user_id == user.id,
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Блокировка не найдена")
    await session.delete(row)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/appointments", response_model=list[AppointmentOut])
async def list_appointments(
    user: PortalUserDep,
    session: AsyncSessionDep,
    settings: SettingsDep,
    organization_id: UUID | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
) -> list[AppointmentOut]:
    oid = _org_id(user, organization_id)
    stmt = select(AppointmentModel).where(
        AppointmentModel.portal_user_id == user.id,
        AppointmentModel.organization_id == oid,
    )
    if status_filter:
        stmt = stmt.where(AppointmentModel.status == status_filter.strip())
    rows = (await session.execute(stmt)).scalars().all()
    tz = settings.app_zoneinfo
    out: list[AppointmentModel] = []
    for r in rows:
        if from_date is not None:
            ld = r.start_time.astimezone(tz).date()
            if ld < from_date:
                continue
        if to_date is not None:
            ld = r.start_time.astimezone(tz).date()
            if ld > to_date:
                continue
        out.append(r)
    out.sort(key=lambda x: x.start_time)
    return [_appointment_to_out(a) for a in out]


def _appointment_to_out(a: AppointmentModel) -> AppointmentOut:
    price = a.service_price
    pf: float | None = None
    if price is not None:
        pf = float(price)
    return AppointmentOut(
        id=a.id,
        portal_user_id=a.portal_user_id,
        organization_id=a.organization_id,
        client_info=dict(a.client_info or {}),
        start_time=a.start_time,
        end_time=a.end_time,
        status=a.status,
        service_price=pf,
    )


@router.patch("/appointments/{appointment_id}/cancel", response_model=AppointmentOut)
async def cancel_appointment(
    appointment_id: UUID,
    user: PortalUserDep,
    session: AsyncSessionDep,
    organization_id: UUID | None = Query(None),
) -> AppointmentOut:
    oid = _org_id(user, organization_id)
    stmt = select(AppointmentModel).where(
        AppointmentModel.id == appointment_id,
        AppointmentModel.portal_user_id == user.id,
        AppointmentModel.organization_id == oid,
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Запись не найдена")
    row.status = "canceled"
    await session.commit()
    await session.refresh(row)
    return _appointment_to_out(row)


@router.get("/stats", response_model=BookingStatsOut)
async def booking_stats(
    user: PortalUserDep,
    session: AsyncSessionDep,
    settings: SettingsDep,
    organization_id: UUID | None = Query(None),
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
) -> BookingStatsOut:
    oid = _org_id(user, organization_id)
    if to_date < from_date:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Некорректный период")
    u0, _ = _day_bounds_utc(from_date, settings)
    _, u1 = _day_bounds_utc(to_date, settings)
    stmt = select(AppointmentModel).where(
        AppointmentModel.portal_user_id == user.id,
        AppointmentModel.organization_id == oid,
        AppointmentModel.start_time >= u0,
        AppointmentModel.start_time < u1,
    )
    rows = (await session.execute(stmt)).scalars().all()

    counts: dict[str, int] = {}
    completed = 0
    revenue = Decimal("0")
    tz = settings.app_zoneinfo
    hour_ctr: Counter[int] = Counter()
    day_ctr: Counter[str] = Counter()

    for a in rows:
        counts[a.status] = counts.get(a.status, 0) + 1
        if a.status == "completed":
            completed += 1
            if a.service_price is not None:
                revenue += Decimal(str(a.service_price))
            local_st = a.start_time.astimezone(tz)
            hour_ctr[local_st.hour] += 1
            day_ctr[local_st.date().isoformat()] += 1

    popular_hours = [{"hour": h, "count": c} for h, c in sorted(hour_ctr.items())]
    completed_by_day = [{"day": d, "count": c} for d, c in sorted(day_ctr.items())]

    return BookingStatsOut(
        period_from=from_date,
        period_to=to_date,
        counts_by_status=counts,
        completed_consultations=completed,
        revenue_total=float(revenue),
        popular_hours=popular_hours,
        completed_by_day=completed_by_day,
    )


@public_router.get("/slots/{user_id}", response_model=PublicSlotsOut)
async def public_available_slots(
    user_id: UUID,
    session: AsyncSessionDep,
    settings: SettingsDep,
    slot_date: date = Query(..., alias="date"),
    organization_id: UUID | None = Query(None),
) -> PublicSlotsOut:
    staff = await session.get(PortalUserModel, user_id)
    if staff is None or not staff.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Сотрудник не найден")
    oid = staff.organization_id
    if oid is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Нет организации")
    if organization_id is not None and organization_id != oid:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Неверная организация")
    cfg_stmt = select(BookingConfigModel).where(
        BookingConfigModel.portal_user_id == user_id,
        BookingConfigModel.organization_id == oid,
    )
    cfg = (await session.execute(cfg_stmt)).scalar_one_or_none()
    duration = int(cfg.appointment_duration) if cfg is not None else 30
    working = dict(cfg.working_hours or {}) if cfg is not None else {}

    day_start, day_end = _day_bounds_utc(slot_date, settings)

    busy_stmt = select(BusySlotModel).where(
        BusySlotModel.portal_user_id == user_id,
        BusySlotModel.end_time > day_start,
        BusySlotModel.start_time < day_end,
    )
    busy_rows = (await session.execute(busy_stmt)).scalars().all()

    ap_stmt = select(AppointmentModel).where(
        AppointmentModel.portal_user_id == user_id,
        AppointmentModel.organization_id == oid,
        AppointmentModel.end_time > day_start,
        AppointmentModel.start_time < day_end,
    )
    ap_rows = (await session.execute(ap_stmt)).scalars().all()

    slots = compute_available_slots(
        target_date=slot_date,
        duration_minutes=duration,
        working_hours=working,
        busy_intervals=_busy_intervals(busy_rows),
        appointment_intervals=_appointment_blocking_intervals(ap_rows),
        settings=settings,
    )
    return PublicSlotsOut(
        date=slot_date,
        portal_user_id=user_id,
        organization_id=oid,
        appointment_duration=duration,
        slots=[PublicSlotItem(start_time=s, end_time=e) for s, e in slots],
    )


def _dt_close(a: datetime, b: datetime, *, max_sec: float = 2.0) -> bool:
    return abs((a.astimezone(_UTC) - b.astimezone(_UTC)).total_seconds()) < max_sec


async def _slot_pair_allowed(
    start: datetime,
    end: datetime,
    slot_date: date,
    staff_uid: UUID,
    oid: UUID,
    settings: Settings,
    session: AsyncSession,
) -> bool:
    """Проверяет, что интервал по-прежнему в списке свободных слотов."""
    day_start, day_end = _day_bounds_utc(slot_date, settings)
    busy_stmt = select(BusySlotModel).where(
        BusySlotModel.portal_user_id == staff_uid,
        BusySlotModel.end_time > day_start,
        BusySlotModel.start_time < day_end,
    )
    busy_rows = (await session.execute(busy_stmt)).scalars().all()
    ap_stmt = select(AppointmentModel).where(
        AppointmentModel.portal_user_id == staff_uid,
        AppointmentModel.organization_id == oid,
        AppointmentModel.end_time > day_start,
        AppointmentModel.start_time < day_end,
    )
    ap_rows = (await session.execute(ap_stmt)).scalars().all()
    cfg_stmt = select(BookingConfigModel).where(
        BookingConfigModel.portal_user_id == staff_uid,
        BookingConfigModel.organization_id == oid,
    )
    cfg = (await session.execute(cfg_stmt)).scalar_one_or_none()
    duration = int(cfg.appointment_duration) if cfg is not None else 30
    working = dict(cfg.working_hours or {}) if cfg is not None else {}
    slots = compute_available_slots(
        target_date=slot_date,
        duration_minutes=duration,
        working_hours=working,
        busy_intervals=_busy_intervals(busy_rows),
        appointment_intervals=_appointment_blocking_intervals(ap_rows),
        settings=settings,
    )
    for a, b in slots:
        if _dt_close(a, start) and _dt_close(b, end):
            return True
    return False


@public_router.post("/appointments", response_model=AppointmentOut, status_code=status.HTTP_201_CREATED)
async def public_create_appointment(
    body: PublicAppointmentCreate,
    session: AsyncSessionDep,
    settings: SettingsDep,
) -> AppointmentOut:
    staff = await session.get(PortalUserModel, body.staff_user_id)
    if staff is None or not staff.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Сотрудник не найден")
    if staff.organization_id is None or staff.organization_id != body.organization_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Неверная организация")
    if body.end_time <= body.start_time:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Некорректный интервал")
    slot_date = body.start_time.astimezone(settings.app_zoneinfo).date()
    ok = await _slot_pair_allowed(
        body.start_time,
        body.end_time,
        slot_date,
        body.staff_user_id,
        body.organization_id,
        settings,
        session,
    )
    if not ok:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Слот недоступен")
    row = AppointmentModel(
        portal_user_id=body.staff_user_id,
        organization_id=body.organization_id,
        client_info=dict(body.client_info or {}),
        start_time=body.start_time,
        end_time=body.end_time,
        status="pending",
    )
    session.add(row)
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        logger.exception("public_create_appointment: commit failed")
        raise
    await session.refresh(row)
    return _appointment_to_out(row)
