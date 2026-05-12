"""Инструменты MCP-стиля для юридического ассистента (OpenAI function calling).

Пакет ``mcp`` в проект не включён; схемы инструментов совместимы с ``chat.completions`` (поле ``tools``).
При появлении полноценного MCP-сервера можно зарегистрировать те же имена и обработчики на стороне сервера."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.repositories.compliance_repositories import SqlAlchemyLegalProfileRepository
from src.infrastructure.repositories.stores import SqlAlchemyKnowledgeRepository

logger = logging.getLogger(__name__)

SEARCH_GARANT_TOOL_NAME = "search_garant_legal_acts"
GET_CHARTER_RULES_TOOL_NAME = "get_charter_rules"


def _uuid_list_from_jsonb(raw: Any) -> list[UUID]:
    if not raw or not isinstance(raw, list):
        return []
    out: list[UUID] = []
    for x in raw:
        try:
            out.append(x if isinstance(x, UUID) else UUID(str(x).strip()))
        except ValueError:
            continue
    return out


def openai_tools_payload() -> list[dict[str, Any]]:
    """Список для ``tools=`` в OpenAI-compatible API."""

    defs = LegalToolRegistry.builtin_definitions()
    return [t.to_openai_dict() for t in defs]


class LegalToolRegistry:
    """Реестр юридических инструментов: JSON-схема + связь с асинхронными обработчиками."""

    @staticmethod
    def builtin_definitions() -> list["_OpenAIToolDef"]:
        return [
            _OpenAIToolDef(
                name=SEARCH_GARANT_TOOL_NAME,
                description=(
                    "Поиск актуальных выдержек из законодательства РФ в системе Гарант по запросу. "
                    "Возвращает текстовые фрагменты для формулировок в протоколах и заключениях."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Поисковый запрос (например, «избрание единоличного исполнительного органа ООО»).",
                        },
                        "doc_type": {
                            "type": "string",
                            "description": "Желаемый тип документа: codex, federal_law, regional, instruction, судебная практика и т.д.",
                        },
                    },
                    "required": ["query"],
                },
            ),
            _OpenAIToolDef(
                name=GET_CHARTER_RULES_TOOL_NAME,
                description=(
                    "Возвращает **charter_rules** из карточки комплаенса и полные тексты документов базы знаний, "
                    "привязанных к профилю (**knowledge_item_ids**). В первую очередь опирайся на раздел "
                    "**knowledge_documents** (устав, протоколы); **charter_rules** — дополнительные ограничения из формы. "
                    "`organization_id` должен совпадать с контекстом запроса."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "organization_id": {
                            "type": "string",
                            "format": "uuid",
                            "description": "Идентификатор организации (должен совпадать с текущей).",
                        },
                    },
                    "required": ["organization_id"],
                },
            ),
        ]


@dataclass(frozen=True, slots=True)
class _OpenAIToolDef:
    name: str
    description: str
    parameters: dict[str, Any]

    def to_openai_dict(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


async def search_garant_legal_acts(query: str, doc_type: str = "") -> str:
    """HTTP-обращение к API Гаранта; при отсутствии конфигурации — демо-текст без сетевого вызова.

    Для боевого режима задайте **GARANT_API_BASE_URL** (базовый URL REST) и **GARANT_API_TOKEN** (Bearer).
    Подстановка заголовков — см. комментарий у ``client.get``.
    """
    q = (query or "").strip()
    dt = (doc_type or "").strip()
    base = os.environ.get("GARANT_API_BASE_URL", "").strip()
    token = os.environ.get("GARANT_API_TOKEN", "").strip()

    if not q:
        return "Пустой запрос к базе законодательства."

    if not base or not token:
        logger.info(
            "Гарант: демо-режим (нет GARANT_API_BASE_URL или GARANT_API_TOKEN). query=%r doc_type=%r",
            q,
            dt,
        )
        return (
            "[Выдержки (демо, API Гаранта не настроен)]\n"
            f"Запрос: {q}\nТип документа (подсказка модели): {dt or '(не указан)'}\n"
            "В рабочем режиме здесь должны быть статьи из актуальной редакции КонсультантПлюс/Гарант. "
            "Задайте переменные окружения **GARANT_API_BASE_URL** и **GARANT_API_TOKEN** для реальных запросов."
        )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Пример вызова: уточните path и параметры по документации вашего договора с Гарант.
            resp = await client.get(
                f"{base.rstrip('/')}/search",
                params={"query": q, "doc_type": dt or None},
                headers={
                    "Authorization": f"Bearer {token}",
                    # "Accept": "application/json",
                },
            )
            resp.raise_for_status()
            # При JSON: распарсьте и соберите текст; пока универсальный fallback:
            ctype = resp.headers.get("content-type", "")
            if "json" in ctype.lower():
                data = resp.json()
                return json.dumps(data, ensure_ascii=False, indent=2)[:16000]
            return (resp.text or "")[:16000]
    except httpx.HTTPStatusError as exc:
        logger.warning("Гарант: HTTP %s", exc.response.status_code)
        return (
            "[Ошибка API Гаранта] Сервис законодательства вернул ошибку HTTP "
            f"{exc.response.status_code}. Сформулируй протокол с оговоркой, что нужна ручная проверка акту."
        )
    except httpx.TimeoutException:
        logger.warning("Гарант: timeout")
        return (
            "[Ошибка API Гаранта] Таймаут при обращении к сервису. "
            "Предупреди пользователя и предложи повторить запрос позже."
        )
    except httpx.RequestError as exc:
        logger.warning("Гарант: сеть недоступна — %s", exc)
        return (
            "[Ошибка API Гаранта] Сеть или DNS недоступны; выдержки из базы получить не удалось. "
            "Укажи в документе, что источники закона должны быть проверены юристом."
        )


async def get_charter_rules(session: AsyncSession, organization_id: UUID) -> str:
    """Загружает **charter_rules** и привязанные к профилю тексты из базы знаний."""

    repo = SqlAlchemyLegalProfileRepository(session, organization_id=organization_id)
    row = await repo.get()
    if row is None:
        body: dict[str, Any] = {
            "found": False,
            "message": "Профиль комплаенса для организации ещё не создан; ограничения устава не заданы.",
            "charter_rules": {},
            "knowledge_documents": [],
        }
        return json.dumps(body, ensure_ascii=False)

    kid = _uuid_list_from_jsonb(row.knowledge_item_ids)
    knowledge_documents: list[dict[str, Any]] = []
    if kid:
        krepo = SqlAlchemyKnowledgeRepository(session, organization_id=organization_id)
        items = await krepo.get_by_ids(kid)
        for it in items:
            text = (it.content or "").strip()
            if len(text) > 20000:
                text = text[:20000] + "\n[… усечено …]"
            knowledge_documents.append(
                {
                    "id": str(it.id),
                    "title": it.title,
                    "content": text,
                },
            )

    return json.dumps(
        {
            "found": True,
            "organization_id": str(organization_id),
            "charter_rules": row.charter_rules or {},
            "knowledge_documents": knowledge_documents,
            "note": "Сначала используй knowledge_documents (привязанная БЗ), затем charter_rules из анкеты.",
        },
        ensure_ascii=False,
    )


async def dispatch_legal_tool(
    *,
    name: str,
    arguments: dict[str, Any],
    session: AsyncSession,
    organization_id: UUID,
) -> str:
    """Выполнение одного инструмента после ответа LLM (**tool_calls**)."""

    if name == SEARCH_GARANT_TOOL_NAME:
        q = str(arguments.get("query", "")).strip()
        dt = str(arguments.get("doc_type", "")).strip()
        return await search_garant_legal_acts(q, dt)

    if name == GET_CHARTER_RULES_TOOL_NAME:
        raw_oid = str(arguments.get("organization_id", "")).strip()
        ctx = organization_id
        try:
            passed = UUID(raw_oid) if raw_oid else ctx
        except ValueError:
            passed = ctx
        if passed != ctx:
            return json.dumps(
                {
                    "error": "organization_id не совпадает с текущей организацией; используются данные только для текущей.",
                    "used_organization_id": str(ctx),
                },
                ensure_ascii=False,
            )
        return await get_charter_rules(session, ctx)

    return json.dumps({"error": f"Неизвестный инструмент: {name}"}, ensure_ascii=False)
