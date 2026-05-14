"""Mini App: роли МИС по chat_id (врач / пациент) поверх JWT miniapp."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.api.dependencies import AsyncSessionDep, SettingsDep
from src.api.routers.miniapp import MiniAppUserDep
from src.infrastructure.models import (
    MedicalDoctorModel,
    MedicalPatientModel,
    MiniAppUserModel,
    PortalUserModel,
)
from src.infrastructure.portal_security import create_mis_patient_access_token

router = APIRouter(prefix="/mis", tags=["miniapp-mis"])


def _miniapp_user_full_name(mini: MiniAppUserModel) -> str:
    fn = (getattr(mini, "first_name", None) or "").strip()
    ln = (getattr(mini, "last_name", None) or "").strip()
    if fn or ln:
        return (f"{fn} {ln}".strip()) or ((mini.name or "").strip() or "Пациент")
    return (mini.name or "").strip() or "Пациент"


async def get_doctor_for_miniapp_user(
    mini: MiniAppUserDep,
    session: AsyncSessionDep,
) -> MedicalDoctorModel | None:
    """Профиль ``MedicalDoctorModel`` для текущего JWT Mini App, если ``chat_id`` совпадает с ``miniapp_chat_id``."""
    cid = (mini.chat_id or "").strip()
    if not cid:
        return None
    pu = (
        await session.execute(
            select(PortalUserModel).where(
                PortalUserModel.organization_id == mini.organization_id,
                PortalUserModel.miniapp_chat_id == cid,
                PortalUserModel.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if pu is None:
        return None
    return (
        await session.execute(
            select(MedicalDoctorModel).where(
                MedicalDoctorModel.portal_user_id == pu.id,
                MedicalDoctorModel.organization_id == mini.organization_id,
                MedicalDoctorModel.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()


class MiniAppMisSessionOut(BaseModel):
    """Определение роли в контексте МИС по совпадению ``miniapp_chat_id`` / ``max_chat_id``.

    Приоритет: **врач** (portal_users.miniapp_chat_id + medical_doctors), иначе **пациент** по ``max_chat_id``,
    иначе ``role=null`` (гость).
    """

    role: Literal["doctor", "patient"] | None = None
    portal_user_id: UUID | None = None
    medical_doctor_id: UUID | None = None
    patient_id: UUID | None = None
    patient_needs_registration: bool = False


class MisAcceptAgreementOut(BaseModel):
    status: Literal["ok"] = "ok"


@router.get("/session", response_model=MiniAppMisSessionOut)
async def mis_miniapp_session(
    mini: MiniAppUserDep,
    session: AsyncSessionDep,
) -> MiniAppMisSessionOut:
    """Сначала врач по ``miniapp_chat_id`` портала; только если не врач — пациент по ``max_chat_id``."""
    doc = await get_doctor_for_miniapp_user(mini, session)
    if doc is not None:
        return MiniAppMisSessionOut(
            role="doctor",
            portal_user_id=doc.portal_user_id,
            medical_doctor_id=doc.id,
            patient_needs_registration=False,
        )

    cid = (mini.chat_id or "").strip()
    oid = mini.organization_id

    if cid:
        stmt_pat = select(MedicalPatientModel).where(
            MedicalPatientModel.organization_id == oid,
            MedicalPatientModel.max_chat_id == cid,
        )
        pat = (await session.execute(stmt_pat)).scalar_one_or_none()
        if pat is not None:
            return MiniAppMisSessionOut(
                role="patient",
                patient_id=pat.id,
                patient_needs_registration=False,
            )

    return MiniAppMisSessionOut(role=None, patient_needs_registration=True)


@router.post("/accept-agreement", response_model=MisAcceptAgreementOut)
async def mis_miniapp_accept_agreement(
    mini: MiniAppUserDep,
    session: AsyncSessionDep,
) -> MisAcceptAgreementOut:
    """Создаёт карту пациента по ``chat_id`` Mini App без врача (``doctor_id`` = NULL), если записи ещё нет.

    Не вызывается для пользователя, у которого уже определён профиль врача МИС.
    """
    doc = await get_doctor_for_miniapp_user(mini, session)
    if doc is not None:
        return MisAcceptAgreementOut()

    cid = (mini.chat_id or "").strip()
    if not cid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="В JWT Mini App отсутствует chat_id",
        )

    stmt = select(MedicalPatientModel).where(
        MedicalPatientModel.organization_id == mini.organization_id,
        MedicalPatientModel.max_chat_id == cid,
    )
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        return MisAcceptAgreementOut()

    full_name = _miniapp_user_full_name(mini)
    row = MedicalPatientModel(
        organization_id=mini.organization_id,
        doctor_id=None,
        full_name=full_name,
        phone=None,
        max_chat_id=cid,
    )
    session.add(row)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
    return MisAcceptAgreementOut()


class MisMiniPatientRow(BaseModel):
    """Краткая карточка пациента для списка в Mini App (врач)."""

    id: UUID
    full_name: str
    phone: str | None = None
    updated_at: datetime


@router.get("/patients", response_model=list[MisMiniPatientRow])
async def list_my_patients_for_miniapp(
    mini: MiniAppUserDep,
    session: AsyncSessionDep,
) -> list[MisMiniPatientRow]:
    """Список пациентов врача (только при совпадении ``chat_id`` с ``portal_users.miniapp_chat_id``)."""
    doc = await get_doctor_for_miniapp_user(mini, session)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступно только врачу: укажите ваш chat_id в разделе МИС портала",
        )
    stmt = (
        select(MedicalPatientModel)
        .where(
            MedicalPatientModel.doctor_id == doc.id,
            MedicalPatientModel.organization_id == doc.organization_id,
        )
        .order_by(MedicalPatientModel.updated_at.desc())
    )
    rows = (await session.scalars(stmt)).all()
    return [
        MisMiniPatientRow(
            id=p.id,
            full_name=p.full_name,
            phone=(p.phone or "").strip() or None,
            updated_at=p.updated_at,
        )
        for p in rows
    ]


class MisPatientBootstrapResponse(BaseModel):
    access_token: str | None = None
    token_type: str = "bearer"
    patient_id: UUID | None = None
    expires_in_minutes: int | None = Field(default=None, description="Срок жизни JWT пациента МИС")


@router.post("/patient-bootstrap", response_model=MisPatientBootstrapResponse)
async def mis_patient_bootstrap(
    mini: MiniAppUserDep,
    session: AsyncSessionDep,
    settings: SettingsDep,
) -> MisPatientBootstrapResponse:
    """Выдаёт JWT пациента МИС, если в организации есть карта с ``max_chat_id`` = chat из Mini App.

    Используется, когда активный сайт организации имеет ``site_kind=mis`` и не нужен отдельный
    шаг ``/mis/auth/max/init`` для уже привязанного пациента.
    """
    cid = (mini.chat_id or "").strip()
    if not cid:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="В JWT Mini App отсутствует chat_id")

    stmt = select(MedicalPatientModel).where(
        MedicalPatientModel.organization_id == mini.organization_id,
        MedicalPatientModel.max_chat_id == cid,
    )
    pat = (await session.execute(stmt)).scalar_one_or_none()
    if pat is None:
        return MisPatientBootstrapResponse(access_token=None, patient_id=None, expires_in_minutes=None)

    minutes = max(1, int(getattr(settings, "mis_patient_jwt_expire_minutes", 60) or 60))
    token = create_mis_patient_access_token(
        patient_id=pat.id,
        organization_id=mini.organization_id,
        secret=settings.portal_jwt_secret,
        expire_minutes=minutes,
    )
    return MisPatientBootstrapResponse(
        access_token=token,
        patient_id=pat.id,
        expires_in_minutes=minutes,
    )
