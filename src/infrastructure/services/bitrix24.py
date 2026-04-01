"""Адаптер CRM Bitrix24 через входящий вебхук REST."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from src.use_cases.interfaces import ICRMService

logger = logging.getLogger(__name__)


class NullCRMService(ICRMService):
    """Заглушка, если вебхук Bitrix24 не настроен (разработка и тесты)."""

    async def create_lead(self, phone: str, name: str, description: str) -> str:
        logger.info(
            "CRM не настроена: лид не отправлен (phone=%s, name=%s)",
            phone,
            name,
        )
        return "mock-no-bitrix"


class Bitrix24CRMAdapter(ICRMService):
    """Создание лида методом crm.lead.add по URL входящего вебхука."""

    def __init__(self, webhook_url: str) -> None:
        # URL вида: https://<портал>.bitrix24.ru/rest/<user>/<token>/crm.lead.add
        self._url = webhook_url.rstrip("/")

    async def create_lead(self, phone: str, name: str, description: str) -> str:
        payload: dict[str, Any] = {
            "fields": {
                "TITLE": f"Лид (AI-агент): {name}",
                "NAME": name.strip() or "Клиент",
                "PHONE": [{"VALUE": phone.strip(), "VALUE_TYPE": "WORK"}],
                "COMMENTS": (description or "")[:8000],
                "OPENED": "Y",
                "SOURCE_ID": "WEB",
            }
        }
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(self._url, json=payload)
            response.raise_for_status()
            data = response.json()
        if "result" not in data:
            msg = f"Bitrix24: неожиданный ответ: {data}"
            raise RuntimeError(msg)
        lead_id = data["result"]
        return str(lead_id)


def build_crm_service(webhook_url: str | None) -> ICRMService:
    """Фабрика порта CRM по настройкам окружения."""
    if webhook_url and webhook_url.strip():
        return Bitrix24CRMAdapter(webhook_url.strip())
    return NullCRMService()
