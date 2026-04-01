"""Celery: автообзвон по очереди dialer_queue (SIP-адаптер без локальных кодеков)."""

from __future__ import annotations

import asyncio
import logging

from src.core.config import get_settings
from src.domain.entities import DialerQueueStatus
from src.infrastructure.database import AsyncSessionLocal
from src.infrastructure.repositories import SqlAlchemyDialerQueueRepository
from src.infrastructure.voice.sip_pipecat_adapter import build_telephony_service

logger = logging.getLogger(__name__)


async def _run_outbound_campaign_async() -> int:
    """Обрабатывает пакет pending-записей; возвращает число обработанных строк."""
    settings = get_settings()
    telephony = build_telephony_service(settings)
    async with AsyncSessionLocal() as session:
        repo = SqlAlchemyDialerQueueRepository(session)
        pending = await repo.list_pending(limit=100)

    processed = 0
    for item in pending:
        if item.id is None:
            continue
        async with AsyncSessionLocal() as s:
            r = SqlAlchemyDialerQueueRepository(s)
            try:
                await r.set_status(item.id, DialerQueueStatus.IN_PROGRESS)
                await s.commit()
            except Exception:
                await s.rollback()
                logger.exception("Не удалось пометить in_progress id=%s", item.id)
                continue

        try:
            await telephony.make_outbound_call(item.phone)
            # TODO: По событию «ответил абонент» от PBX поднять Pipecat и писать в Redis под новым session_id.
            final_status = DialerQueueStatus.COMPLETED
        except Exception:
            logger.exception("Ошибка исходящего вызова на %s", item.phone)
            final_status = DialerQueueStatus.FAILED

        async with AsyncSessionLocal() as s:
            r = SqlAlchemyDialerQueueRepository(s)
            try:
                await r.set_status(item.id, final_status)
                await s.commit()
            except Exception:
                await s.rollback()
                logger.exception("Не удалось обновить статус id=%s", item.id)
        processed += 1

    return processed


def run_outbound_campaign_sync() -> int:
    """Синхронная обёртка для Celery worker."""
    return asyncio.run(_run_outbound_campaign_async())
