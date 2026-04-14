"""Отправка уведомлений продавцу о заказе из публичной витрины (MAX / Telegram / VK)."""

from __future__ import annotations

import logging
import random

import httpx

from src.core.config import Settings
from src.domain import system_setting_keys as sk
from src.infrastructure.services.max_messenger import MaxMessengerClient
from src.use_cases.interfaces import ISettingsRepository

logger = logging.getLogger(__name__)


async def resolve_telegram_bot_token(repo: ISettingsRepository, app: Settings) -> str:
    db = (await repo.get_value(sk.TELEGRAM_BOT_TOKEN) or "").strip()
    if db:
        return db
    return (app.telegram_bot_token or "").strip()


async def send_telegram_order_message(token: str, chat_id: str, text: str) -> None:
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN не задан (панель «Настройки» или TELEGRAM_BOT_TOKEN в .env)")
    cid = str(chat_id).strip()
    if not cid:
        raise ValueError("Пустой chat_id Telegram")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload: dict[str, object] = {"chat_id": cid, "text": text}
    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        body = response.json()
    if not body.get("ok"):
        raise ValueError(str(body))


async def send_vk_order_message(access_token: str, peer_id: int, text: str) -> None:
    if not access_token:
        raise ValueError("VK_API_ACCESS_TOKEN не задан в окружении (.env)")
    url = "https://api.vk.com/method/messages.send"
    params = {
        "access_token": access_token,
        "v": "5.199",
        "peer_id": peer_id,
        "message": text,
        "random_id": random.randint(1, 2_147_483_647),
    }
    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
    err = data.get("error")
    if err:
        raise ValueError(str(err))


async def send_max_order_message(client: MaxMessengerClient, chat_id: int, text: str) -> None:
    await client.send_message(chat_id, text)
