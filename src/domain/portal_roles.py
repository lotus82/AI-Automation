"""Роли портала и ключи разделов для прав сотрудников."""

from __future__ import annotations

# Роли
ROLE_SUPER_ADMIN = "super_admin"
ROLE_ORG_ADMIN = "org_admin"
ROLE_DIRECTOR = "director"
ROLE_EMPLOYEE = "employee"

PORTAL_ROLES = (
    ROLE_SUPER_ADMIN,
    ROLE_ORG_ADMIN,
    ROLE_DIRECTOR,
    ROLE_EMPLOYEE,
)

# Ключи разделов панели (совпадают с path без ведущего /)
SECTION_QA_ANALYTICS = "qa-analytics"
SECTION_AI_TRAINER = "ai-trainer"
SECTION_LEADGEN = "leadgen"
SECTION_QUESTIONNAIRES = "questionnaires"
SECTION_FORMS = "forms"
SECTION_INTEGRATIONS = "integrations"
SECTION_ROLES = "roles"
SECTION_SETTINGS = "settings"
SECTION_LOGS = "logs"
SECTION_KNOWLEDGE = "knowledge"
SECTION_SCHEDULE = "schedule"
SECTION_BOOKINGS = "bookings"
SECTION_SHOPS = "shops"
SECTION_MIS = "mis"
SECTION_SITES = "sites"

ALL_SECTION_KEYS = (
    SECTION_QA_ANALYTICS,
    SECTION_AI_TRAINER,
    SECTION_LEADGEN,
    SECTION_QUESTIONNAIRES,
    SECTION_FORMS,
    SECTION_SHOPS,
    SECTION_SITES,
    SECTION_INTEGRATIONS,
    SECTION_ROLES,
    SECTION_SETTINGS,
    SECTION_LOGS,
    SECTION_KNOWLEDGE,
    SECTION_SCHEDULE,
    SECTION_BOOKINGS,
    SECTION_MIS,
)

# Полный доступ для администратора организации (и супер-админа)
ORG_ADMIN_SECTIONS = list(ALL_SECTION_KEYS)

# Директор: аналитика, опросники, пользователи организации; остальное — по политике
DIRECTOR_DEFAULT_SECTIONS = [
    SECTION_QA_ANALYTICS,
    SECTION_QUESTIONNAIRES,
    SECTION_FORMS,
    SECTION_SHOPS,
    SECTION_KNOWLEDGE,
    SECTION_BOOKINGS,
    SECTION_MIS,
]


def sections_for_new_employee() -> list[str]:
    """Минимум по умолчанию при создании сотрудника без явных прав."""
    return [SECTION_QA_ANALYTICS]
