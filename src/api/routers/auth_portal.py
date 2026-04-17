"""Вход в портал и профиль (JWT)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from starlette.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.api.dependencies import AsyncSessionDep, SettingsDep
from src.api.dependencies_portal import PortalUserDep
from src.api.schemas.portal import (
    PortalLoginRequest,
    PortalLoginResponse,
    PortalPasswordChangeRequest,
    PortalUserMe,
)
from src.infrastructure.models import MedicalDoctorModel, OrganizationModel, PortalUserModel
from src.infrastructure.portal_access import effective_sections
from src.infrastructure.portal_security import (
    create_portal_access_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=PortalLoginResponse)
async def portal_login(
    body: PortalLoginRequest,
    session: AsyncSessionDep,
    settings: SettingsDep,
) -> PortalLoginResponse:
    username = body.username.strip()
    if not username:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Укажите логин")

    stmt = (
        select(PortalUserModel)
        .where(PortalUserModel.username == username)
        .options(selectinload(PortalUserModel.organization))
    )
    user = (await session.execute(stmt)).scalar_one_or_none()
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
        )
    if user.organization_id is not None:
        org = user.organization
        if org is None:
            org = await session.get(OrganizationModel, user.organization_id)
        if org is None or not org.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Организация отключена",
            )

    token = create_portal_access_token(
        user_id=user.id,
        role=user.role,
        organization_id=user.organization_id,
        secret=settings.portal_jwt_secret,
        expire_minutes=settings.portal_jwt_expire_minutes,
    )
    return PortalLoginResponse(
        access_token=token,
        expires_in_minutes=settings.portal_jwt_expire_minutes,
    )


@router.get("/me", response_model=PortalUserMe)
async def portal_me(user: PortalUserDep, session: AsyncSessionDep) -> PortalUserMe:
    org_name = None
    org_display = None
    org_inn = None
    if user.organization_id and user.organization:
        org = user.organization
        org_name = org.name
        od = (org.display_name or "").strip()
        org_display = od or None
        org_inn = (org.inn or "").strip() or None
    doc_stmt = (
        select(MedicalDoctorModel.id)
        .where(
            MedicalDoctorModel.portal_user_id == user.id,
            MedicalDoctorModel.is_active.is_(True),
        )
        .limit(1)
    )
    medical_doctor_id = (await session.execute(doc_stmt)).scalar_one_or_none()
    return PortalUserMe(
        id=user.id,
        username=user.username,
        role=user.role,
        display_name=user.display_name,
        organization_id=user.organization_id,
        organization_name=org_name,
        organization_display_name=org_display,
        organization_inn=org_inn,
        permissions=user.permissions or {},
        sections=effective_sections(user),
        medical_doctor_id=medical_doctor_id,
    )


@router.patch(
    "/me/password",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def portal_change_own_password(
    body: PortalPasswordChangeRequest,
    user: PortalUserDep,
    session: AsyncSessionDep,
) -> Response:
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неверный текущий пароль")
    user.password_hash = hash_password(body.new_password)
    session.add(user)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
