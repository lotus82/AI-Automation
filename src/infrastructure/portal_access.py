"""Вычисление доступных разделов панели по роли и permissions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.domain.portal_roles import (
    ALL_SECTION_KEYS,
    DIRECTOR_DEFAULT_SECTIONS,
    ROLE_DIRECTOR,
    ROLE_EMPLOYEE,
    ROLE_ORG_ADMIN,
    ROLE_SUPER_ADMIN,
    sections_for_new_employee,
)

if TYPE_CHECKING:
    from src.infrastructure.models import PortalUserModel


def effective_sections(user: PortalUserModel) -> list[str]:
    """Список ключей разделов для UI и проверок."""
    if user.role == ROLE_SUPER_ADMIN or user.role == ROLE_ORG_ADMIN:
        return list(ALL_SECTION_KEYS)
    if user.role == ROLE_DIRECTOR:
        base = list(DIRECTOR_DEFAULT_SECTIONS)
        extra = _sections_from_permissions(user.permissions)
        for s in extra:
            if s in ALL_SECTION_KEYS and s not in base:
                base.append(s)
        return base
    if user.role == ROLE_EMPLOYEE:
        sec = _sections_from_permissions(user.permissions)
        return sec if sec else sections_for_new_employee()
    return list(ALL_SECTION_KEYS)


def _sections_from_permissions(permissions: dict[str, Any] | None) -> list[str]:
    if not permissions or not isinstance(permissions, dict):
        return []
    raw = permissions.get("sections")
    if not isinstance(raw, list):
        return []
    return [str(x) for x in raw if str(x) in ALL_SECTION_KEYS]
