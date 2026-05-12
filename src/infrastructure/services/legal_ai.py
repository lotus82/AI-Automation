"""Генерация юридических документов с LLM и вызовом инструментов (Гарант, устав)."""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings, llm_system_time_prefix
from src.domain import system_setting_keys as sk
from src.domain.default_system_prompts import FALLBACK_LEGAL_AI_PROMPT
from src.domain.system_roles import get_legal_ai_system_prompt, parse_roles_config_raw, resolve_role_prompt_from_roles_config
from src.infrastructure.models import LegalDocType, LegalDocumentModel
from src.infrastructure.repositories.compliance_repositories import (
    SqlAlchemyLegalDocumentRepository,
    SqlAlchemyLegalProfileRepository,
)
from src.infrastructure.repositories.stores import (
    PostgresSettingsRepository,
    SqlAlchemyKnowledgeRepository,
)
from src.infrastructure.services.dynamic_llm import DynamicLLMService
from src.infrastructure.services.mcp_legal_tools import dispatch_legal_tool, openai_tools_payload

logger = logging.getLogger(__name__)

_MAX_LEGAL_TOOL_ROUNDS = 10

_DOCUMENT_TYPE_META: dict[str, tuple[str, LegalDocType]] = {
    "protocol_director_change": ("Протокол общего собрания: смена директора", LegalDocType.PROTOCOL),
    "protocol": ("Протокол общего собрания", LegalDocType.PROTOCOL),
}


def resolve_document_kind(document_type_key: str) -> tuple[str, LegalDocType]:
    """Человекочитаемый заголовок и enum для сохранения в БД."""

    key = (document_type_key or "").strip().lower()
    if key in _DOCUMENT_TYPE_META:
        return _DOCUMENT_TYPE_META[key]
    title = key.replace("_", " ").strip().title() or "Юридический документ"
    return title, LegalDocType.OTHER


def _knowledge_ids_from_profile(profile: Any) -> list[UUID]:
    raw = getattr(profile, "knowledge_item_ids", None) or []
    if not isinstance(raw, list):
        return []
    out: list[UUID] = []
    for x in raw:
        try:
            out.append(x if isinstance(x, UUID) else UUID(str(x).strip()))
        except ValueError:
            continue
    return out


class LegalAIService:
    """Оркестрация промпта, tool calling и сохранения **LegalDocumentModel**."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def generate_protocol(
        self,
        *,
        session: AsyncSession,
        redis: Redis,
        organization_id: UUID,
        agenda: str,
        attendees: str,
        role_id: UUID | None,
        document_type_key: str,
        extra_context: dict[str, Any] | None = None,
        llm_temperature: float | None = 0.25,
    ) -> tuple[str, LegalDocumentModel]:
        """Строит протокол (или смежный текст), сохраняя черновик в ``legal_documents``.

        Системный промпт: роль из **SYSTEM_ROLES_CONFIG** по **LegalProfileModel.system_role_id** (строковый ``id``),
        иначе — **get_legal_ai_system_prompt** по ``role_id`` запроса; при выбранном id без совпадения в конфиге —
        **FALLBACK_LEGAL_AI_PROMPT**.

        Тексты из базы знаний (**knowledge_item_ids** профиля) добавляются в пользовательский промпт как
        «Контекст организации (Устав/Протоколы)»; инструмент ``get_charter_rules`` отдаёт те же привязки из БД.
        """
        repo_settings = PostgresSettingsRepository(session, redis, organization_id=organization_id)
        llm = DynamicLLMService(self._settings, repo_settings)

        profile_repo = SqlAlchemyLegalProfileRepository(session, organization_id=organization_id)
        profile = await profile_repo.get()

        persona: str
        profile_role_key = (str(profile.system_role_id).strip() if profile and profile.system_role_id else "") or ""
        if profile_role_key:
            raw_cfg = (await repo_settings.get_value(sk.SYSTEM_ROLES_CONFIG) or "").strip()
            cfg = parse_roles_config_raw(raw_cfg)
            resolved = resolve_role_prompt_from_roles_config(cfg, profile_role_key)
            if resolved:
                persona = resolved
            else:
                persona = FALLBACK_LEGAL_AI_PROMPT
        else:
            persona = (await get_legal_ai_system_prompt(repo_settings, role_id=role_id)).strip()

        system_text = llm_system_time_prefix(None) + persona

        org_kb_lines: list[str] = []
        kid_uuids = _knowledge_ids_from_profile(profile) if profile else []
        if kid_uuids:
            krepo = SqlAlchemyKnowledgeRepository(session, organization_id=organization_id)
            items = await krepo.get_by_ids(kid_uuids)
            if items:
                org_kb_lines.append("### Контекст организации (Устав/Протоколы)")
                for it in items:
                    body = (it.content or "").strip()
                    if len(body) > 24000:
                        body = body[:24000] + "\n\n[… фрагмент усечён …]"
                    org_kb_lines.append(f"#### {it.title}\n\n{body}")
                org_kb_lines.append("")

        extra = dict(extra_context or {})
        user_lines: list[str] = []
        user_lines.extend(org_kb_lines)
        user_lines.extend(
            [
                "Составь текст юридического документа по следующим данным.",
                f"Тип шаблона (ключ): `{document_type_key}`.",
                "",
                "**Повестка / задача заседания:**",
                agenda.strip() or "(не указано)",
                "",
                "**Участники / присутствующие (как передано клиентом):**",
                attendees.strip() or "(не указано)",
                "",
                "**Дополнительный контекст (JSON):**",
                json.dumps(extra, ensure_ascii=False, indent=2),
                "",
                "Обязательно вызови инструмент `get_charter_rules` для текущей организации "
                "(там же приоритетно отдаются привязанные к профилю документы базы знаний), "
                "и при необходимости уточняющего права вызови `search_garant_legal_acts`. "
                "В итоге верни только готовый текст документа (без обрамляющего JSON).",
            ]
        )
        user_content = "\n".join(user_lines)

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_text},
            {"role": "user", "content": user_content},
        ]
        tools = openai_tools_payload()

        final_text = ""
        for _round in range(_MAX_LEGAL_TOOL_ROUNDS):
            text, tool_calls = await llm.generate_sales_response_with_tools(
                messages,
                tools=tools,
                temperature=llm_temperature,
            )
            prefix = "[Нет API-ключа]"
            if (text or "").startswith(prefix):
                logger.warning("LegalAIService: LLM недоступен (ключи организации)")
                raise RuntimeError(
                    "Не задан ключ LLM-провайдера в настройках организации или ответ недоступен."
                )

            if not tool_calls:
                final_text = (text or "").strip()
                break

            openai_tool_calls: list[dict[str, Any]] = []
            for tc in tool_calls:
                openai_tool_calls.append(
                    {
                        "id": tc.tool_call_id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                        },
                    }
                )

            messages.append(
                {"role": "assistant", "content": text or "", "tool_calls": openai_tool_calls}
            )

            for tc in tool_calls:
                try:
                    payload = await dispatch_legal_tool(
                        name=tc.name,
                        arguments=tc.arguments,
                        session=session,
                        organization_id=organization_id,
                    )
                except Exception as exc:
                    logger.exception("Сбой выполнения юридического инструмента %s", tc.name)
                    payload = json.dumps(
                        {"ok": False, "error": str(exc)},
                        ensure_ascii=False,
                    )
                messages.append(
                    {"role": "tool", "tool_call_id": tc.tool_call_id, "content": payload}
                )
        else:
            logger.warning(
                "LegalAIService: превышен лимит итераций tool calling (%s)", _MAX_LEGAL_TOOL_ROUNDS
            )
            final_text = (
                final_text.strip()
                or "Не удалось завершить генерацию протокола: слишком много циклов вызова инструментов."
            )

        doc_title, doc_type = resolve_document_kind(document_type_key)
        doc_repo = SqlAlchemyLegalDocumentRepository(session, organization_id=organization_id)
        saved = await doc_repo.create(
            title=doc_title,
            doc_type=doc_type,
            content=final_text,
        )
        return final_text, saved
