"""Создание учётной записи главного администратора при первом запуске."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.portal_roles import ROLE_SUPER_ADMIN
from src.infrastructure.models import PortalUserModel
from src.infrastructure.portal_security import hash_password


async def ensure_portal_bootstrap(session: AsyncSession) -> None:
    """Если нет пользователя ``admin``, создаёт супер-админа (логин/пароль ``admin`` / ``admin``)."""
    r = await session.execute(select(PortalUserModel.id).where(PortalUserModel.username == "admin"))
    if r.scalar_one_or_none() is not None:
        return
    session.add(
        PortalUserModel(
            organization_id=None,
            username="admin",
            password_hash=hash_password("admin"),
            role=ROLE_SUPER_ADMIN,
            display_name="Главный администратор",
            permissions={},
            is_active=True,
        )
    )
    await session.commit()
