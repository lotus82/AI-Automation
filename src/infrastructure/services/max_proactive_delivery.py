"""Адаптер доставки проактивных сообщений в MAX (порт сценария расписания)."""

from __future__ import annotations

from src.infrastructure.services.max_messenger import MaxMessengerClient
from src.use_cases.interfaces import IProactiveDeliveryMessenger


class MaxProactiveDeliveryMessenger(IProactiveDeliveryMessenger):
    """Обёртка над ``MaxMessengerClient.send_message`` (числовой chat_id в строке)."""

    def __init__(self, client: MaxMessengerClient) -> None:
        self._client = client

    async def send_plain_text(self, chat_id: str, text: str) -> None:
        cid = int((chat_id or "").strip())
        await self._client.send_message(cid, text)
