"""Разбор текстовых файлов для модуля «Читатель» (книги / главы / стихи)."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from src.infrastructure.models import DocumentNodeModel


# Главу проверять раньше книги: строка «=== 1 ===» тоже начинается с «==», иначе
# паттерн книги ошибочно даёт лишний узел book с заголовком «= 1».
_BOOK_RE = re.compile(r"^==(?!=)\s*(.+?)\s*==$")
# Том / раздел верхнего уровня: «= Ветхий завет =» (один знак =), не путать с «== книга ==».
_TOME_RE = re.compile(r"^=\s*(.+?)\s*=$")
_CHAPTER_RE = re.compile(r"^===\s*(.+?)\s*===$")
_VERSE_RE = re.compile(r"^(\d+)\s+(.+)$")


@dataclass
class ParseState:
    #: Последний узел «= том =» — родитель для следующих «== книга ==»
    current_tome_id: uuid.UUID | None = None
    current_book_id: uuid.UUID | None = None
    current_chapter_id: uuid.UUID | None = None
    order_book: int = 0
    order_nested_book: int = 0
    order_chapter: int = 0
    order_verse: int = 0
    order_text: int = 0


class DocumentParserService:
    """Парсит .txt в плоский список узлов с parent_id (для bulk insert)."""

    @staticmethod
    def parse_text(document_id: uuid.UUID, raw: str) -> list[DocumentNodeModel]:
        lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        state = ParseState()
        nodes: list[DocumentNodeModel] = []

        for line in lines:
            s = line.strip()
            if not s:
                continue

            m_ch = _CHAPTER_RE.match(s)
            if m_ch:
                if state.current_book_id is None:
                    msg = "Сначала укажите книгу строкой вида «== Название ==»"
                    raise ValueError(msg)
                state.order_chapter += 1
                state.order_verse = 0
                state.order_text = 0
                cid = uuid.uuid4()
                state.current_chapter_id = cid
                title_part = m_ch.group(1).strip()
                ch_title = title_part if title_part.lower().startswith("глава") else f"Глава {title_part}"
                nodes.append(
                    DocumentNodeModel(
                        id=cid,
                        document_id=document_id,
                        parent_id=state.current_book_id,
                        title=ch_title,
                        content=None,
                        node_type="chapter",
                        order_index=state.order_chapter,
                    ),
                )
                continue

            m_book = _BOOK_RE.match(s)
            if m_book:
                parent_id = state.current_tome_id
                if parent_id:
                    state.order_nested_book += 1
                    book_oi = state.order_nested_book
                else:
                    state.order_book += 1
                    book_oi = state.order_book
                state.order_chapter = 0
                state.order_verse = 0
                state.order_text = 0
                bid = uuid.uuid4()
                state.current_book_id = bid
                state.current_chapter_id = None
                nodes.append(
                    DocumentNodeModel(
                        id=bid,
                        document_id=document_id,
                        parent_id=parent_id,
                        title=m_book.group(1).strip(),
                        content=None,
                        node_type="book",
                        order_index=book_oi,
                    ),
                )
                continue

            # «= Название тома =» — только если строка не начинается с «==» (уже разобрано выше).
            m_tome = _TOME_RE.match(s) if s.startswith("=") and not s.startswith("==") else None
            if m_tome:
                state.order_book += 1
                state.order_nested_book = 0
                state.order_chapter = 0
                state.order_verse = 0
                state.order_text = 0
                tid = uuid.uuid4()
                state.current_tome_id = tid
                state.current_book_id = None
                state.current_chapter_id = None
                nodes.append(
                    DocumentNodeModel(
                        id=tid,
                        document_id=document_id,
                        parent_id=None,
                        title=m_tome.group(1).strip(),
                        content=None,
                        node_type="book",
                        order_index=state.order_book,
                    ),
                )
                continue

            m_ver = _VERSE_RE.match(s)
            if m_ver:
                if state.current_book_id is None:
                    msg = "Сначала укажите книгу строкой вида «== Название ==»"
                    raise ValueError(msg)
                # Стихи часто идут сразу после «== книга ==» без «=== глава ===» — создаём неявную главу.
                if state.current_chapter_id is None:
                    state.order_chapter += 1
                    state.order_verse = 0
                    state.order_text = 0
                    cid = uuid.uuid4()
                    state.current_chapter_id = cid
                    nodes.append(
                        DocumentNodeModel(
                            id=cid,
                            document_id=document_id,
                            parent_id=state.current_book_id,
                            title="Глава 1",
                            content=None,
                            node_type="chapter",
                            order_index=state.order_chapter,
                        ),
                    )
                state.order_verse += 1
                num, rest = m_ver.group(1), m_ver.group(2).strip()
                vid = uuid.uuid4()
                nodes.append(
                    DocumentNodeModel(
                        id=vid,
                        document_id=document_id,
                        parent_id=state.current_chapter_id,
                        title=f"Стих {num}",
                        content=rest,
                        node_type="verse",
                        order_index=state.order_verse,
                    ),
                )
                continue

            # Прочий текст — под главой, книгой или томом «= … =»
            parent = state.current_chapter_id or state.current_book_id or state.current_tome_id
            if parent is None:
                msg = (
                    "Произвольный текст допустим только после тома (= … =), книги (== … ==) или главы (=== … ===)"
                )
                raise ValueError(msg)
            state.order_text += 1
            tid = uuid.uuid4()
            nodes.append(
                DocumentNodeModel(
                    id=tid,
                    document_id=document_id,
                    parent_id=parent,
                    title="Текст",
                    content=s,
                    node_type="text",
                    order_index=state.order_text,
                ),
            )

        if not nodes:
            msg = (
                "Файл не содержит распознанных блоков (ожидаются «= том =», «== книга ==», "
                "«=== глава ===», стихи «1 текст…»)"
            )
            raise ValueError(msg)
        return nodes
