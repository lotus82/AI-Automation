"""Допустимые ключи встраиваемых модулей Mini App (страницы сайта).

Расширяйте по мере реализации UI; в конструкторе показываются как «скоро».
"""

from __future__ import annotations

# Пустая строка / None — модуль не задан.
MINIAPP_EMBED_MODULE_CHOICES: tuple[tuple[str, str], ...] = (
    ("", "Нет встроенного модуля"),
    ("knowledge", "База знаний"),
    ("roles", "Роли и промпты"),
    ("questionnaires", "Опросники"),
    ("forms", "Формы"),
    ("shops", "Магазины"),
    ("integrations", "Интеграции"),
    ("schedule", "Расписание (сценарии)"),
    ("bookings", "Записи (список/аналитика)"),
    ("bots", "Боты и каналы"),
    ("logs", "Логи"),
    ("applications", "Приложения"),
    ("sites", "Сайты"),
    ("mis", "МИС"),
    ("chats", "Чаты"),
)

ALLOWED_EMBED_MODULE_KEYS: frozenset[str] = frozenset(k for k, _ in MINIAPP_EMBED_MODULE_CHOICES if k)


def normalize_embed_module(raw: str | None) -> str | None:
    s = (raw or "").strip()
    if not s:
        return None
    if s not in ALLOWED_EMBED_MODULE_KEYS:
        return None
    return s
