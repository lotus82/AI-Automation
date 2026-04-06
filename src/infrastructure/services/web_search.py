"""Веб-поиск через DuckDuckGo (легковесно, без локального браузера)."""

from __future__ import annotations

import asyncio
import importlib.util
import logging
from typing import Any

from src.use_cases.interfaces import ISearchService

logger = logging.getLogger(__name__)

# Защита от переполнения контекста LLM
_MAX_RESULT_CHARS = 12_000


def _sync_ddgs_text(query: str, max_results: int) -> list[dict[str, Any]]:
    """Синхронный вызов DDGS.text в отдельном потоке (в пакете v8 нет AsyncDDGS)."""
    from duckduckgo_search import DDGS

    with DDGS() as ddgs:
        raw = ddgs.text(query, max_results=max_results)
    return list(raw) if raw else []


class DuckDuckGoSearchService(ISearchService):
    """Текстовый поиск DuckDuckGo; не блокирует event loop (asyncio.to_thread)."""

    async def search(self, query: str, max_results: int = 3) -> str:
        q = (query or "").strip()
        if not q:
            return "Пустой поисковый запрос; уточни формулировку."

        n = max(1, min(int(max_results), 10))

        if importlib.util.find_spec("duckduckgo_search") is None:
            logger.warning("Пакет duckduckgo-search не установлен")
            return (
                "Веб-поиск недоступен: в окружении не установлен пакет duckduckgo-search. "
                "Обратись к администратору."
            )

        try:
            items = await asyncio.to_thread(_sync_ddgs_text, q, n)
        except TimeoutError as exc:
            logger.warning("Таймаут веб-поиска: %s", exc)
            return "Поиск прервался по таймауту. Попробуй сформулировать запрос короче или повтори позже."
        except Exception as exc:  # noqa: BLE001 — сеть/DuckDuckGo: не роняем агента
            logger.exception("Ошибка веб-поиска DuckDuckGo")
            return (
                "Не удалось выполнить поиск в интернете (сеть или сервис недоступен). "
                f"Кратко: {exc!s}"
            )

        if not items:
            return "По запросу не найдено подходящих публичных сниппетов."

        lines: list[str] = []
        for i, item in enumerate(items, start=1):
            title = str(item.get("title") or "").strip()
            href = str(item.get("href") or "").strip()
            body = str(item.get("body") or "").strip()
            lines.append(f"{i}. {title}\n   URL: {href}\n   Фрагмент: {body}")

        text = "\n\n".join(lines)
        if len(text) > _MAX_RESULT_CHARS:
            text = text[: _MAX_RESULT_CHARS] + "\n\n… (результаты усечены)"
        return text
