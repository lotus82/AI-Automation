"""Зависимости FastAPI: текущий пациент МИС (JWT с типом ``mis_patient``)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status

from src.api.dependencies import AsyncSessionDep
from src.infrastructure.models import MedicalPatientModel


async def get_current_patient(request: Request, session: AsyncSessionDep) -> MedicalPatientModel:
    """Доступно только для маршрутов под префиксом ``/api/mis/patient-session`` (см. middleware)."""
    payload = getattr(request.state, "mis_patient_token_payload", None)
    if not payload or payload.get("typ") != "mis_patient":
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация пациента (токен MAX)",
        )
    try:
        pid = UUID(str(payload.get("sub")))
    except (ValueError, TypeError):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный токен пациента",
        ) from None
    row = await session.get(MedicalPatientModel, pid)
    if row is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Пациент не найден",
        )
    org_claim = payload.get("org_id")
    if org_claim and str(row.organization_id) != str(org_claim):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Организация не совпадает с токеном",
        )
    return row


MisPatientDep = Annotated[MedicalPatientModel, Depends(get_current_patient)]
