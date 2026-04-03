"""Правила входящих сообщений MAX в групповых чатах: только по явному @упоминанию.

Инфраструктурный слой: до вызова ``ProcessTextMessageUseCase`` текст очищается от @username;
в память (Redis/PostgreSQL) попадает уже очищенная реплика.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from src.domain import system_setting_keys as sk
from src.use_cases.interfaces import ISettingsRepository

logger = logging.getLogger(__name__)


def _sender_user_id(sender: dict[str, Any] | None) -> int | None:
    if not isinstance(sender, dict):
        return None
    for key in ("user_id", "id"):
        if key not in sender:
            continue
        try:
            return int(sender[key])  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
    return None


def detect_max_group_chat(
    *,
    chat_id: int,
    recipient: dict[str, Any],
    sender: dict[str, Any] | None,
) -> bool:
    """Эвристика группы для MAX.

    Отрицательный ``chat_id`` — как правило группа (в т.ч. если тип в payload ошибочно ``dialog``).

    Личка: явные ``chat_type`` вроде ``dialog`` / ``private`` / ``direct`` при **положительном**
    ``chat_id`` — не группа, даже если ``chat_id`` не совпадает с ``user_id`` отправителя.
    Иначе: ``chat_id == user_id`` → личка; нет ``user_id`` в отправителе → не считаем группой.
    """
    ct = str(
        recipient.get("chat_type") or recipient.get("type") or recipient.get("chat_type_name") or ""
    ).strip().lower()
    if ct in ("group", "channel", "crowd", "chat", "public"):
        return True

    cid = int(chat_id)
    if cid < 0:
        return True

    # Личка: у MAX часто chat_type=dialog при положительном chat_id, но chat_id ≠ user_id.
    if ct in ("dialog", "private", "direct"):
        return False

    sid = _sender_user_id(sender)
    if sid is None:
        return False
    if cid == sid:
        return False
    return True


def _mention_variants(bot_username: str) -> list[str]:
    """Варианты строки для поиска и удаления (с @ и без)."""
    u = (bot_username or "").strip()
    if not u:
        return []
    u = u.replace("\uff20", "@")
    seen: list[str] = []
    for cand in (u, u.lstrip("@"), f"@{u.lstrip('@')}"):
        if cand and cand not in seen:
            seen.append(cand)
    return seen


def strip_max_bot_mention(text: str, bot_username: str) -> str:
    """Удаляет все варианты упоминания (без учёта регистра), сжимает пробелы."""
    result = (text or "").strip()
    for variant in _mention_variants(bot_username):
        pattern = re.compile(re.escape(variant), re.IGNORECASE)
        result = pattern.sub(" ", result)
    return " ".join(result.split()).strip()


async def apply_max_group_mention_rules(
    settings_repo: ISettingsRepository,
    *,
    raw_user_text: str,
    is_group_chat: bool,
) -> str | None:
    """Для личного чата — исходный текст. Для группы — только если есть упоминание; иначе ``None`` (не обрабатывать)."""
    text = (raw_user_text or "").strip()
    if not text:
        return None

    if not is_group_chat:
        return text

    bot = (await settings_repo.get_value(sk.MAX_BOT_USERNAME) or "").strip()
    if not bot:
        logger.info(
            "MAX: групповой чат, MAX_BOT_USERNAME не задан — сообщение пропущено (укажите упоминание в настройках панели)."
        )
        return None

    norm_text = text.replace("\uff20", "@")
    lower = norm_text.lower()
    if not any(v.lower() in lower for v in _mention_variants(bot)):
        logger.info(
            "MAX: группа, в тексте нет упоминания бота (%s), пропуск. Фрагмент: %r",
            bot,
            norm_text[:160],
        )
        return None

    cleaned = strip_max_bot_mention(norm_text, bot)
    if not cleaned:
        # Только упоминание без вопроса — всё равно отвечаем нейтрально.
        cleaned = "Здравствуйте, нужна помощь по оборудованию."
    return cleaned
