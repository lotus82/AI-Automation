"""Сценарии использования для лидов."""

from __future__ import annotations

from datetime import UTC, datetime

from src.domain.entities import Lead, LeadStatus
from src.domain.exceptions import DomainValidationError
from src.use_cases.interfaces import ILeadRepository


class CreateLeadUseCase:
    """Создание лида: валидация входных данных, доменная сущность, сохранение через порт."""

    def __init__(self, lead_repository: ILeadRepository) -> None:
        self._leads = lead_repository

    async def execute(
        self,
        *,
        name: str,
        phone_number: str,
        status: LeadStatus | None = None,
    ) -> Lead:
        cleaned_name = name.strip()
        if not cleaned_name:
            raise DomainValidationError("Имя лида не может быть пустым")
        if len(cleaned_name) > 255:
            raise DomainValidationError("Имя лида не должно превышать 255 символов")

        cleaned_phone = phone_number.strip()
        if not cleaned_phone:
            raise DomainValidationError("Номер телефона не может быть пустым")
        if len(cleaned_phone) > 64:
            raise DomainValidationError("Номер телефона не должен превышать 64 символа")

        effective_status = status or LeadStatus.NEW
        now = datetime.now(UTC)

        lead = Lead(
            name=cleaned_name,
            phone_number=cleaned_phone,
            status=effective_status,
            created_at=now,
        )
        return await self._leads.save(lead)
