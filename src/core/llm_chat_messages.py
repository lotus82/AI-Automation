"""Унификация формата сообщений для Chat Completions (OpenAI / DeepSeek)."""

from __future__ import annotations


def memory_history_to_openai_messages(history: list[dict]) -> list[dict[str, str]]:
    """Преобразует сырые записи памяти чата в список ``{"role","content"}`` без склейки в одну строку.

    Поля вроде ``user_display`` отбрасываются — провайдеру нужны только роль и текст.
    """
    out: list[dict[str, str]] = []
    for turn in history:
        role = turn.get("role")
        content = turn.get("content")
        if role in ("user", "assistant") and isinstance(content, str) and content.strip():
            out.append({"role": role, "content": content.strip()})
    return out
