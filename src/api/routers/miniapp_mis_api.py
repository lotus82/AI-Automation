"""Mini App: роли МИС по chat_id (врач / пациент) поверх JWT miniapp."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from src.api.dependencies import AsyncSessionDep, SettingsDep
from src.api.routers.miniapp import MiniAppUserDep
from src.infrastructure.models import MedicalDoctorModel, MedicalPatientModel, PortalUserModel
from src.infrastructure.portal_security import create_mis_patient_access_token

router = APIRouter(prefix="/mis", tags=["miniapp-mis"])


class MiniAppMisSessionOut(BaseModel):
    """Определение роли в контексте МИС по совпадению ``miniapp_chat_id`` / ``max_chat_id``."""

    role: Literal["guest", "doctor", "patient"]
    portal_user_id: UUID | None = None
    medical_doctor_id: UUID | None = None
    patient_id: UUID | None = None
    patient_needs_registration: bool = False


@router.get("/session", response_model=MiniAppMisSessionOut)
async def mis_miniapp_session(
    mini: MiniAppUserDep,
    session: AsyncSessionDep,
) -> MiniAppMisSessionOut:
    """По JWT Mini App и ``chat_id`` определяет врача (профиль МИС + ``portal_users.miniapp_chat_id``)
    или пациента (``medical_patients.max_chat_id``)."""
    cid = (mini.chat_id or "").strip()
    oid = mini.organization_id

    if cid:
        stmt_pu = select(PortalUserModel).where(
            PortalUserModel.organization_id == oid,
            PortalUserModel.miniapp_chat_id == cid,
            PortalUserModel.is_active.is_(True),
        )
        pu = (await session.execute(stmt_pu)).scalar_one_or_none()
        if pu is not None:
            stmt_doc = select(MedicalDoctorModel).where(
                MedicalDoctorModel.portal_user_id == pu.id,
                MedicalDoctorModel.organization_id == oid,
                MedicalDoctorModel.is_active.is_(True),
            )
            doc = (await session.execute(stmt_doc)).scalar_one_or_none()
            if doc is not None:
                return MiniAppMisSessionOut(
                    role="doctor",
                    portal_user_id=pu.id,
                    medical_doctor_id=doc.id,
                )

        stmt_pat = select(MedicalPatientModel).where(
            MedicalPatientModel.organization_id == oid,
            MedicalPatientModel.max_chat_id == cid,
        )
        pat = (await session.execute(stmt_pat)).scalar_one_or_none()
        if pat is not None:
            return MiniAppMisSessionOut(
                role="patient",
                patient_id=pat.id,
            )

    return MiniAppMisSessionOut(role="guest", patient_needs_registration=True)


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
