"""Область организации для API настроек и базы знаний."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status

from src.infrastructure.models import PortalUserModel


def resolve_organization_scope(
    user: PortalUserModel,
    query_organization_id: UUID | None,
) -> UUID | None:
    """``None`` — глобальные данные (только супер-админ без выбора организации). Иначе id организации."""
    if user.organization_id is None:
        return query_organization_id
    if query_organization_id is not None and query_organization_id != user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для данных другой организации",
        )
    return user.organization_id
