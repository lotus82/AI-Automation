"""Мост SIP ↔ Pipecat: заготовка под RTP/UDP или WebSocket от Asterisk/FreeSWITCH.

Тяжёлые аудиокодеки на CPU приложения не используются — поток PCM ожидается от АТС/медиа-сервера.
"""

from __future__ import annotations

import logging
from uuid import uuid4

from src.core.config import Settings
from src.use_cases.interfaces import ITelephonyService

logger = logging.getLogger(__name__)


class SIPPipecatAdapter:
    """Точка расширения: приём медиа и подключение к VoicePipelineOrchestrator.

    # TODO: Реализовать приём RTP (PCMU/PCMA) или бинарного потока по WebSocket от моста Asterisk.
    # TODO: Согласовать семплрейт и сериализацию кадров с существующим Pipecat pipeline.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def log_sip_target(self) -> None:
        """Диагностика: куда будет направлен сигналинг (без паролей в логах)."""
        host = (self._settings.sip_server_ip or "").strip()
        user = (self._settings.sip_user or "").strip()
        if host:
            logger.info(
                "SIPPipecatAdapter: целевой хост %s, пользователь %s (пароль из env не логируется)",
                host,
                user or "(не задан)",
            )
        else:
            logger.warning(
                "SIPPipecatAdapter: SIP_SERVER_IP не задан — используйте заглушку или настройте транк",
            )


class AsteriskTelephonyService(ITelephonyService):
    """Телефония при подключённом Asterisk (ARI слушается в FastAPI lifespan).

    Сигналинг и медиа — на стороне Asterisk; приложение только RTP+Pipecat.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._adapter = SIPPipecatAdapter(settings)

    async def make_outbound_call(self, phone: str) -> str:
        self._adapter.log_sip_target()
        # TODO: POST /channels (Originate) в ARI с контекстом исходящего.
        ext_id = f"ari-stub-out-{phone[:16]}"
        logger.info("AsteriskTelephonyService: исходящий пока не реализован, phone=%s", phone)
        return ext_id

    async def handle_inbound_call(self, call_id: str) -> str:
        self._adapter.log_sip_target()
        session_id = str(uuid4())
        logger.debug("AsteriskTelephonyService: inbound call_id=%s → session_id=%s", call_id, session_id)
        return session_id


class StubSIPTelephonyService(ITelephonyService):
    """Заглушка: не открывает реальный SIP, возвращает синтетические идентификаторы.

    Подключите реализацию с AMI/ARI Asterisk или ESL FreeSWITCH вместо этой заглушки.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._adapter = SIPPipecatAdapter(settings)

    async def make_outbound_call(self, phone: str) -> str:
        self._adapter.log_sip_target()
        ext_id = f"stub-out-{uuid4().hex[:12]}"
        logger.info(
            "StubSIP: имитация исходящего вызова на %s, внешний id=%s (нет реального INVITE)",
            phone,
            ext_id,
        )
        # TODO: После ответа абонента поднять Pipecat с персоной консультанта и записью в Redis.
        return ext_id

    async def handle_inbound_call(self, call_id: str) -> str:
        self._adapter.log_sip_target()
        session_id = str(uuid4())
        logger.info(
            "StubSIP: зарегистрирован входящий call_id=%s → session_id=%s",
            call_id,
            session_id,
        )
        return session_id


def build_telephony_service(settings: Settings) -> ITelephonyService:
    """Фабрика телефонии: Asterisk+ARI при заданных переменных, иначе заглушка."""
    if (
        (settings.asterisk_url or "").strip()
        and (settings.asterisk_ari_user or "").strip()
        and (settings.asterisk_ari_password or "").strip()
    ):
        return AsteriskTelephonyService(settings)
    return StubSIPTelephonyService(settings)
