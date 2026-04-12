"""Текущий пользователь портала из JWT (после middleware)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.api.dependencies import AsyncSessionDep
from src.domain.portal_roles import ROLE_DIRECTOR, ROLE_ORG_ADMIN, ROLE_SUPER_ADMIN
from src.infrastructure.models import OrganizationModel, PortalUserModel


async def get_portal_user(request: Request, session: AsyncSessionDep) -> PortalUserModel:
    payload = getattr(request.state, "portal_token_payload", None)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется авторизация")
    try:
        uid = UUID(str(payload["sub"]))
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Недействительный токен") from e

    stmt = (
        select(PortalUserModel)
        .where(PortalUserModel.id == uid)
        .options(selectinload(PortalUserModel.organization))
    )
    user = (await session.execute(stmt)).scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Пользователь не найден или отключён")
    if user.organization_id is not None:
        org = user.organization
        if org is None:
            org = await session.get(OrganizationModel, user.organization_id)
        if org is None or not org.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Организация отключена")
    return user


PortalUserDep = Annotated[PortalUserModel, Depends(get_portal_user)]


def require_portal_roles(*roles: str):
    async def _inner(user: PortalUserDep) -> PortalUserModel:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав",
            )
        return user

    return _inner


SuperAdminDep = Annotated[PortalUserModel, Depends(require_portal_roles(ROLE_SUPER_ADMIN))]
OrgAdminDep = Annotated[PortalUserModel, Depends(require_portal_roles(ROLE_ORG_ADMIN))]
DirectorDep = Annotated[PortalUserModel, Depends(require_portal_roles(ROLE_DIRECTOR))]

# Администратор организации или директор (для части операций с пользователями)
OrgManagerDep = Annotated[PortalUserModel, Depends(require_portal_roles(ROLE_ORG_ADMIN, ROLE_DIRECTOR))]
