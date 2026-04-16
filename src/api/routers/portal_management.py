"""Супер-админ: организации. Администратор организации / директор: пользователи."""

from __future__ import annotations

import re
import uuid as uuid_lib
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from starlette.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.api.dependencies import AsyncSessionDep
from src.api.dependencies_portal import OrgManagerDep, PortalUserDep, SuperAdminDep
from src.api.schemas.portal import (
    OrganizationCreate,
    OrganizationPatch,
    OrganizationPublic,
    PortalUserCreate,
    PortalUserPatch,
    PortalUserPasswordReset,
    PortalUserPublic,
)
from src.domain.portal_roles import (
    ROLE_DIRECTOR,
    ROLE_EMPLOYEE,
    ROLE_ORG_ADMIN,
    ROLE_SUPER_ADMIN,
    sections_for_new_employee,
)
from src.infrastructure.models import OrganizationModel, PortalUserModel
from src.infrastructure.portal_security import hash_password

router = APIRouter(prefix="/portal", tags=["portal"])


def _slug_base(name: str, explicit: str | None) -> str:
    if explicit and explicit.strip():
        raw = explicit.strip().lower()
    else:
        raw = name.strip().lower()
    s = re.sub(r"[^a-z0-9\-]+", "-", raw, flags=re.I)
    s = re.sub(r"-+", "-", s).strip("-")
    return (s[:120] if s else "org").lower()


async def _unique_org_slug(session: AsyncSessionDep, base: str) -> str:
    candidate = base
    for _ in range(20):
        existing = await session.scalar(select(OrganizationModel.id).where(OrganizationModel.slug == candidate))
        if existing is None:
            return candidate
        candidate = f"{base}-{uuid_lib.uuid4().hex[:6]}"
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Не удалось сгенерировать slug")


def _user_to_public(u: PortalUserModel) -> PortalUserPublic:
    return PortalUserPublic(
        id=u.id,
        username=u.username,
        role=u.role,
        display_name=u.display_name,
        is_active=u.is_active,
        permissions=u.permissions or {},
        created_at=u.created_at,
    )


def _org_to_public(org: OrganizationModel) -> OrganizationPublic:
    return OrganizationPublic(
        id=org.id,
        name=org.name,
        display_name=(org.display_name or "").strip() or None,
        slug=org.slug,
        is_active=org.is_active,
        created_at=org.created_at,
    )


@router.get("/organizations", response_model=list[OrganizationPublic])
async def list_organizations(
    _: SuperAdminDep,
    session: AsyncSessionDep,
) -> list[OrganizationPublic]:
    r = await session.execute(select(OrganizationModel).order_by(OrganizationModel.created_at.desc()))
    rows = r.scalars().all()
    return [_org_to_public(x) for x in rows]


@router.post("/organizations", response_model=OrganizationPublic, status_code=status.HTTP_201_CREATED)
async def create_organization(
    body: OrganizationCreate,
    _: SuperAdminDep,
    session: AsyncSessionDep,
) -> OrganizationPublic:
    base = _slug_base(body.name, body.slug)
    slug = await _unique_org_slug(session, base)

    uname = body.admin_username.strip()
    taken = await session.scalar(select(PortalUserModel.id).where(PortalUserModel.username == uname))
    if taken is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Логин администратора уже занят")

    org_dn = (body.organization_display_name or "").strip() or None
    org = OrganizationModel(
        name=body.name.strip(),
        display_name=org_dn,
        slug=slug,
        is_active=True,
    )
    session.add(org)
    await session.flush()

    from src.infrastructure.org_settings_seed import seed_organization_settings_from_global

    await seed_organization_settings_from_global(session, org.id)

    admin = PortalUserModel(
        organization_id=org.id,
        username=uname,
        password_hash=hash_password(body.admin_password),
        role=ROLE_ORG_ADMIN,
        display_name=(body.admin_display_name or "").strip() or None,
        permissions={},
        is_active=True,
    )
    session.add(admin)
    await session.commit()
    await session.refresh(org)
    return _org_to_public(org)


@router.patch("/organizations/{org_id}", response_model=OrganizationPublic)
async def patch_organization(
    org_id: UUID,
    body: OrganizationPatch,
    _: SuperAdminDep,
    session: AsyncSessionDep,
) -> OrganizationPublic:
    if body.name is None and body.organization_display_name is None and body.is_active is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Укажите хотя бы одно поле: name, organization_display_name или is_active",
        )
    org = await session.get(OrganizationModel, org_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Организация не найдена")
    if body.name is not None:
        org.name = body.name.strip()
    if body.organization_display_name is not None:
        org.display_name = (body.organization_display_name or "").strip() or None
    if body.is_active is not None:
        org.is_active = body.is_active
    session.add(org)
    await session.commit()
    await session.refresh(org)
    return _org_to_public(org)


@router.get("/users", response_model=list[PortalUserPublic])
async def list_org_users(
    actor: PortalUserDep,
    session: AsyncSessionDep,
    organization_id: UUID | None = Query(default=None, description="Только для super_admin: фильтр по организации"),
) -> list[PortalUserPublic]:
    if actor.role == ROLE_SUPER_ADMIN:
        stmt = select(PortalUserModel).options(selectinload(PortalUserModel.organization))
        if organization_id is not None:
            stmt = stmt.where(PortalUserModel.organization_id == organization_id)
        else:
            stmt = stmt.where(PortalUserModel.organization_id.isnot(None))
        stmt = stmt.order_by(PortalUserModel.created_at.desc())
        rows = (await session.execute(stmt)).scalars().all()
        return [_user_to_public(u) for u in rows]

    if actor.organization_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет организации")

    stmt = (
        select(PortalUserModel)
        .where(PortalUserModel.organization_id == actor.organization_id)
        .order_by(PortalUserModel.created_at.desc())
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [_user_to_public(u) for u in rows]


@router.post("/users", response_model=PortalUserPublic, status_code=status.HTTP_201_CREATED)
async def create_org_user(
    body: PortalUserCreate,
    actor: OrgManagerDep,
    session: AsyncSessionDep,
) -> PortalUserPublic:
    if actor.role == ROLE_DIRECTOR and body.role != ROLE_EMPLOYEE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Директор может создавать только пользователей с ролью «сотрудник»",
        )
    if actor.organization_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет организации")

    uname = body.username.strip()
    taken = await session.scalar(select(PortalUserModel.id).where(PortalUserModel.username == uname))
    if taken is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Логин уже занят")

    perms: dict = {}
    if body.role == ROLE_EMPLOYEE:
        perms["sections"] = body.sections if body.sections else sections_for_new_employee()
    elif body.role == ROLE_DIRECTOR and body.sections:
        perms["sections"] = body.sections

    user = PortalUserModel(
        organization_id=actor.organization_id,
        username=uname,
        password_hash=hash_password(body.password),
        role=body.role,
        display_name=(body.display_name or "").strip() or None,
        permissions=perms,
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return _user_to_public(user)


@router.patch("/users/{user_id}", response_model=PortalUserPublic)
async def patch_org_user(
    user_id: UUID,
    body: PortalUserPatch,
    actor: PortalUserDep,
    session: AsyncSessionDep,
) -> PortalUserPublic:
    if actor.role not in (ROLE_SUPER_ADMIN, ROLE_ORG_ADMIN, ROLE_DIRECTOR):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав")

    target = await session.get(PortalUserModel, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")

    if actor.role == ROLE_SUPER_ADMIN:
        pass
    elif actor.organization_id != target.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к пользователю")

    if target.role == ROLE_ORG_ADMIN and actor.role != ROLE_SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Изменять администратора организации может только главный администратор",
        )

    if actor.role == ROLE_DIRECTOR:
        if target.role != ROLE_EMPLOYEE:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Директор может редактировать только сотрудников",
            )

    if body.is_active is not None:
        if target.id == actor.id and not body.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нельзя отключить самого себя")
        target.is_active = body.is_active

    if body.display_name is not None:
        target.display_name = body.display_name.strip() or None

    if body.sections is not None:
        if target.role == ROLE_EMPLOYEE:
            target.permissions = {**(target.permissions or {}), "sections": body.sections}
        elif target.role == ROLE_DIRECTOR:
            target.permissions = {**(target.permissions or {}), "sections": body.sections}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Разделы задаются только для директора и сотрудника",
            )

    session.add(target)
    await session.commit()
    await session.refresh(target)
    return _user_to_public(target)


@router.post(
    "/users/{user_id}/password",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def reset_user_password(
    user_id: UUID,
    body: PortalUserPasswordReset,
    actor: PortalUserDep,
    session: AsyncSessionDep,
) -> Response:
    target = await session.get(PortalUserModel, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")

    if actor.role == ROLE_SUPER_ADMIN:
        pass
    elif actor.role == ROLE_ORG_ADMIN:
        if actor.organization_id != target.organization_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа")
        if target.role == ROLE_ORG_ADMIN and target.id != actor.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Сброс пароля другого администратора организации недоступен",
            )
    elif actor.role == ROLE_DIRECTOR:
        if actor.organization_id != target.organization_id or target.role != ROLE_EMPLOYEE:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа")
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав")

    target.password_hash = hash_password(body.new_password)
    session.add(target)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
