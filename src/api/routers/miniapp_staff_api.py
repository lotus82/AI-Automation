"""Mini App: режим сотрудника (chat_id JWT совпадает с ``portal_users.miniapp_chat_id``).

Маршруты монтируются под ``/api/miniapp`` → ``/staff/...``.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from starlette.responses import Response

from src.api.dependencies import AsyncSessionDep, RedisDep, SettingsDep
from src.api.routers.bookings import _appointment_to_out, _day_bounds_utc
from src.api.routers.miniapp import MiniAppUserDep
from src.api.schemas.bookings import (
    AppointmentOut,
    BookingConfigOut,
    BookingConfigUpsert,
    BusySlotCreate,
    BusySlotOut,
)
from src.infrastructure.models import (
    AppointmentModel,
    BookingConfigModel,
    BusySlotModel,
    PortalUserModel,
)
from src.infrastructure.services.booking_max_notify import notify_client_booking_canceled

router = APIRouter(prefix="/staff", tags=["miniapp-staff"])


async def _portal_by_miniapp_chat(
    mini: MiniAppUserDep,
    session: AsyncSessionDep,
) -> PortalUserModel | None:
    cid = (mini.chat_id or "").strip()
    if not cid:
        return None
    stmt = select(PortalUserModel).where(
        PortalUserModel.organization_id == mini.organization_id,
        PortalUserModel.miniapp_chat_id == cid,
        PortalUserModel.is_active.is_(True),
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def require_staff_portal(
    mini: MiniAppUserDep,
    session: AsyncSessionDep,
) -> PortalUserModel:
    pu = await _portal_by_miniapp_chat(mini, session)
    if pu is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Режим сотрудника недоступен: в панели укажите ваш MAX chat_id "
                "(тот же id, что у Web App в мессенджере)."
            ),
        )
    return pu


StaffPortalDep = Annotated[PortalUserModel, Depends(require_staff_portal)]


class MiniAppStaffSessionOut(BaseModel):
    is_staff: bool
    portal_user_id: UUID | None = None
    display_name: str | None = None


@router.get("/session", response_model=MiniAppStaffSessionOut)
async def staff_session(
    mini: MiniAppUserDep,
    session: AsyncSessionDep,
) -> MiniAppStaffSessionOut:
    pu = await _portal_by_miniapp_chat(mini, session)
    if pu is None:
        return MiniAppStaffSessionOut(is_staff=False)
    return MiniAppStaffSessionOut(
        is_staff=True,
        portal_user_id=pu.id,
        display_name=(pu.display_name or "").strip() or None,
    )


def _staff_org_id(staff: PortalUserModel) -> UUID:
    if staff.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="У сотрудника не задана организация",
        )
    return staff.organization_id


@router.get("/bookings/config", response_model=BookingConfigOut)
async def staff_booking_config_get(
    staff: StaffPortalDep,
    session: AsyncSessionDep,
) -> BookingConfigOut:
    oid = _staff_org_id(staff)
    stmt = select(BookingConfigModel).where(
        BookingConfigModel.portal_user_id == staff.id,
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


@router.put("/bookings/config", response_model=BookingConfigOut)
async def staff_booking_config_put(
    body: BookingConfigUpsert,
    staff: StaffPortalDep,
    session: AsyncSessionDep,
) -> BookingConfigOut:
    oid = _staff_org_id(staff)
    stmt = select(BookingConfigModel).where(
        BookingConfigModel.portal_user_id == staff.id,
        BookingConfigModel.organization_id == oid,
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        row = BookingConfigModel(
            portal_user_id=staff.id,
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


@router.get("/bookings/busy-slots", response_model=list[BusySlotOut])
async def staff_list_busy_slots(
    staff: StaffPortalDep,
    session: AsyncSessionDep,
    settings: SettingsDep,
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
) -> list[BusySlotOut]:
    stmt = select(BusySlotModel).where(BusySlotModel.portal_user_id == staff.id)
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


@router.post("/bookings/busy-slots", response_model=BusySlotOut, status_code=status.HTTP_201_CREATED)
async def staff_create_busy_slot(
    body: BusySlotCreate,
    staff: StaffPortalDep,
    session: AsyncSessionDep,
) -> BusySlotOut:
    if body.end_time <= body.start_time:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="end_time должен быть позже start_time")
    row = BusySlotModel(
        portal_user_id=staff.id,
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


@router.delete("/bookings/busy-slots/{slot_id}", response_class=Response)
async def staff_delete_busy_slot(
    slot_id: UUID,
    staff: StaffPortalDep,
    session: AsyncSessionDep,
) -> Response:
    stmt = select(BusySlotModel).where(
        BusySlotModel.id == slot_id,
        BusySlotModel.portal_user_id == staff.id,
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Блокировка не найдена")
    await session.delete(row)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/bookings/appointments", response_model=list[AppointmentOut])
async def staff_list_appointments(
    staff: StaffPortalDep,
    session: AsyncSessionDep,
    settings: SettingsDep,
    status_filter: str | None = Query(None, alias="status"),
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
) -> list[AppointmentOut]:
    oid = _staff_org_id(staff)
    stmt = select(AppointmentModel).where(
        AppointmentModel.portal_user_id == staff.id,
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


@router.patch("/bookings/appointments/{appointment_id}/cancel", response_model=AppointmentOut)
async def staff_cancel_appointment(
    appointment_id: UUID,
    staff: StaffPortalDep,
    session: AsyncSessionDep,
    settings: SettingsDep,
    redis: RedisDep,
) -> AppointmentOut:
    oid = _staff_org_id(staff)
    stmt = select(AppointmentModel).where(
        AppointmentModel.id == appointment_id,
        AppointmentModel.portal_user_id == staff.id,
        AppointmentModel.organization_id == oid,
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Запись не найдена")
    row.status = "canceled"
    await session.commit()
    await session.refresh(row)
    await notify_client_booking_canceled(
        session=session,
        redis=redis,
        settings=settings,
        organization_id=oid,
        appointment=row,
        client_info=dict(row.client_info or {}),
    )
    return _appointment_to_out(row)
