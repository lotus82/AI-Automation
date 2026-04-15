"""Копирование глобальных system_settings в organization_settings при создании организации."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.domain import system_setting_keys as sk
from src.infrastructure.models import OrganizationSettingModel, SystemSettingModel


async def seed_organization_settings_from_global(session: AsyncSession, organization_id: UUID) -> None:
    """Дублирует все строки ``system_settings`` в ``organization_settings`` для новой организации."""
    now = datetime.now(get_settings().app_zoneinfo)
    rows = (await session.scalars(select(SystemSettingModel))).all()
    for g in rows:
        if g.key in sk.SKIP_ORG_SEED_KEYS:
            continue
        session.add(
            OrganizationSettingModel(
                organization_id=organization_id,
                key=g.key,
                value=g.value,
                description=g.description or "",
                updated_at=now,
            )
        )
    await session.flush()
