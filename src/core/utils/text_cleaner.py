"""Очистка ответов LLM от Markdown перед MAX, БД и TTS."""

from __future__ import annotations

import re

# Предкомпиляция: синхронные вызовы не блокируют event loop дольше, чем сам CPU-участок.

# Заборные блоки ```...``` (опциональный язык после открывающих кавычек)
_RE_FENCED = re.compile(r"```[\w]*\n?[\s\S]*?```", re.MULTILINE)

# Картинки ![alt](url) и ссылки [text](url) — оставляем видимый текст
_RE_IMAGE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_RE_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")

# Инлайн-код: один или несколько бэктиков (``code``)
_RE_INLINE_CODE = re.compile(r"`+([^`]*?)`+")

# ATX-заголовки: убираем ведущие #, текст строки сохраняем
_RE_ATX_HEADER = re.compile(r"^[ \t]*#{1,6}[ \t]+(.+?)[ \t]*$", re.MULTILINE)

# Горизонтальные линии --- / *** / ___
_RE_HR = re.compile(
    r"^[ \t]*(?:\*[ \t]*){3,}$|^[ \t]*(?:-[ \t]*){3,}$|^[ \t]*(?:_[ \t]*){3,}$",
    re.MULTILINE,
)

# Жирный и зачёркнутый
_RE_BOLD_STAR = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
_RE_BOLD_UNDER = re.compile(r"__(.+?)__", re.DOTALL)
_RE_STRIKE = re.compile(r"~~(.+?)~~", re.DOTALL)

# Курсив: не пересекаемся с ** (обрабатываем после снятия жирного, итеративно)
_RE_ITALIC_STAR = re.compile(r"(?<!\*)\*(?!\*)([^*\n]+?)(?<!\*)\*(?!\*)", re.DOTALL)
_RE_ITALIC_UNDER = re.compile(r"(?<!_)_(?!_)([^_\n]+?)(?<!_)_(?!_)", re.DOTALL)

# Строка из одних * / # / смешанного «украшения»
_RE_DECOR_LINE = re.compile(r"^[ \t]*[*#_\-]{2,}[ \t]*$", re.MULTILINE)

# Оставшиеся одиночные * или # как отдельные «символы разметки» (между пробелами/границами строки)
_RE_LOOSE_STAR = re.compile(r"(?:^|[ \t])\*+(?=[ \t]|$)", re.MULTILINE)
_RE_LOOSE_HASH = re.compile(r"(?:^|[ \t])#+(?=[ \t]|$)", re.MULTILINE)


def remove_markdown(text: str) -> str:
    """Удаляет типичную разметку Markdown, сохраняя пунктуацию и переводы строк.

    Подходит для синхронного вызова из async-кода (лёгкая CPU-работа).
    """
    if not text:
        return ""

    s = text.replace("\r\n", "\n").replace("\r", "\n")

    s = _RE_FENCED.sub(" ", s)
    s = _RE_IMAGE.sub(r"\1", s)
    s = _RE_LINK.sub(r"\1", s)
    s = _RE_INLINE_CODE.sub(r"\1", s)
    s = _RE_ATX_HEADER.sub(lambda m: m.group(1).strip(), s)
    s = _RE_HR.sub("", s)
    s = _RE_DECOR_LINE.sub("", s)

    # Несколько проходов: вложенные ** и * снимаются поэтапно
    for _ in range(6):
        prev = s
        s = _RE_BOLD_STAR.sub(r"\1", s)
        s = _RE_BOLD_UNDER.sub(r"\1", s)
        s = _RE_STRIKE.sub(r"\1", s)
        s = _RE_ITALIC_STAR.sub(r"\1", s)
        s = _RE_ITALIC_UNDER.sub(r"\1", s)
        if s == prev:
            break

    s = _RE_LOOSE_STAR.sub(" ", s)
    s = _RE_LOOSE_HASH.sub(" ", s)

    # Сжимаем только пробелы внутри строк, переводы строк сохраняем
    lines: list[str] = []
    for line in s.split("\n"):
        lines.append(re.sub(r"[ \t]{2,}", " ", line).strip())
    s = "\n".join(lines)
    return s.strip()
