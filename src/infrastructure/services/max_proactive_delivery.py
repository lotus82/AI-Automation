"""Адаптер доставки проактивных сообщений в MAX (порт сценария расписания)."""

from __future__ import annotations

from src.infrastructure.services.max_messenger import MaxMessengerClient
from src.use_cases.interfaces import IProactiveDeliveryMessenger


class MaxProactiveDeliveryMessenger(IProactiveDeliveryMessenger):
    """Обёртка над ``MaxMessengerClient.send_message`` (числовой chat_id в строке)."""

    def __init__(self, client: MaxMessengerClient) -> None:
        self._client = client

    async def send_plain_text(self, chat_id: str, text: str) -> None:
        raw = (chat_id or "").strip()
        if not raw or raw == "__MINIAPP_BIRTHDAYS__":
            msg = f"max_proactive: некорректный chat_id для отправки: {chat_id!r}"
            raise ValueError(msg)
        try:
            cid = int(raw)
        except ValueError as e:
            msg = f"max_proactive: chat_id должен быть целым ID чата MAX, получено: {chat_id!r}"
            raise ValueError(msg) from e
        await self._client.send_message(cid, text)
