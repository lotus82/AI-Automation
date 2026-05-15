"""Синхронизация даты рождения между Mini App (mini_app_users) и картой пациента МИС."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.models import MedicalPatientModel, MiniAppUserModel


async def sync_birth_date_by_chat(
    session: AsyncSession,
    *,
    organization_id: UUID,
    chat_id: str | None,
    birth_date: date | None,
) -> None:
    """Записывает ``birth_date`` в mini_app_users и medical_patients с тем же ``chat_id`` / ``max_chat_id``."""
    cid = (chat_id or "").strip()
    if not cid:
        return

    user = (
        await session.execute(
            select(MiniAppUserModel).where(
                MiniAppUserModel.organization_id == organization_id,
                MiniAppUserModel.chat_id == cid,
            )
        )
    ).scalar_one_or_none()
    if user is not None:
        user.birth_date = birth_date
        session.add(user)

    patient = (
        await session.execute(
            select(MedicalPatientModel).where(
                MedicalPatientModel.organization_id == organization_id,
                MedicalPatientModel.max_chat_id == cid,
            )
        )
    ).scalar_one_or_none()
    if patient is not None:
        patient.birth_date = birth_date
        session.add(patient)
