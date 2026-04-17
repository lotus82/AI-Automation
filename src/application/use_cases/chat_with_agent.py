"""Оркестрация диалога агента: LLM + вызовы действий интеграций (tools)."""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

from src.application.interfaces.providers.llm_provider import ChatMessage, ILLMProvider
from src.core.config import llm_system_time_prefix
from src.application.use_cases.execute_action import ExecuteActionUseCase
from src.application.use_cases.generate_llm_tools import GenerateLLMToolsUseCase
from src.domain.entities.integration import Integration
from src.domain.exceptions.integration_exceptions import (
    ActionNotFoundError,
    IntegrationCallError,
)
from src.domain.interfaces.repositories.integration_repo import IIntegrationRepository

logger = logging.getLogger(__name__)

_DEFAULT_MAX_ITERATIONS = 5


class ChatWithAgentUseCase:
    """Цикл: LLM → при необходимости выполнение HTTP-действий → снова LLM."""

    def __init__(
        self,
        llm_provider: ILLMProvider,
        integration_repo: IIntegrationRepository,
        generate_tools_use_case: GenerateLLMToolsUseCase,
        execute_action_use_case: ExecuteActionUseCase,
        *,
        max_iterations: int = _DEFAULT_MAX_ITERATIONS,
    ) -> None:
        self._llm = llm_provider
        self._integration_repo = integration_repo
        self._generate_tools = generate_tools_use_case
        self._execute_action = execute_action_use_case
        self._max_iterations = max_iterations

    async def execute_messages(
        self,
        system_prompt: str,
        chat_history: list[ChatMessage],
        user_message: str,
        integration_ids: list[UUID],
        *,
        client_timezone_id: str | None = None,
    ) -> list[ChatMessage]:
        """Сообщения после всех раундов tool calls, **без** финального ответа ассистента (его даёт ``stream_response``)."""
        messages, _final = await self._run_until_final_assistant(
            system_prompt,
            chat_history,
            user_message,
            integration_ids,
            client_timezone_id=client_timezone_id,
        )
        return messages

    async def execute(
        self,
        system_prompt: str,
        chat_history: list[ChatMessage],
        user_message: str,
        integration_ids: list[UUID],
        *,
        client_timezone_id: str | None = None,
    ) -> str:
        """Текст финального ответа ассистента (один нестриминговый вызов LLM на финале)."""
        _messages, final = await self._run_until_final_assistant(
            system_prompt,
            chat_history,
            user_message,
            integration_ids,
            client_timezone_id=client_timezone_id,
        )
        return final.content or ""

    async def _run_until_final_assistant(
        self,
        system_prompt: str,
        chat_history: list[ChatMessage],
        user_message: str,
        integration_ids: list[UUID],
        *,
        client_timezone_id: str | None = None,
    ) -> tuple[list[ChatMessage], ChatMessage]:
        integrations = await self._load_integrations(integration_ids)
        tools = self._generate_tools.execute(integrations)
        full_system = llm_system_time_prefix(client_timezone_id) + system_prompt
        messages: list[ChatMessage] = [
            ChatMessage(role="system", content=full_system),
            *chat_history,
            ChatMessage(role="user", content=user_message),
        ]
        response_msg: ChatMessage | None = None
        for iteration in range(self._max_iterations):
            response_msg = await self._llm.generate_response(messages, tools)
            if not response_msg.tool_calls:
                return messages, response_msg
            messages.append(response_msg)
            for tc in response_msg.tool_calls:
                tool_message = await self._execute_single_tool_call(integrations, tc)
                messages.append(tool_message)
            logger.debug(
                "chat_with_agent: iteration=%s completed tool round, next LLM call",
                iteration + 1,
            )
        logger.warning(
            "chat_with_agent: stopped after max_iterations=%s (last reply may be incomplete)",
            self._max_iterations,
        )
        if response_msg is None:
            return messages, ChatMessage(role="assistant", content="", tool_calls=None)
        return messages, response_msg

    async def _load_integrations(self, integration_ids: list[UUID]) -> list[Integration]:
        out: list[Integration] = []
        for iid in integration_ids:
            entity = await self._integration_repo.get_by_id(iid)
            out.append(entity)
        return out

    async def _execute_single_tool_call(
        self,
        integrations: list[Integration],
        tool_call: dict[str, Any],
    ) -> ChatMessage:
        raw_id = tool_call.get("id")
        fallback_tool_call_id = (
            raw_id if isinstance(raw_id, str) else (str(raw_id) if raw_id is not None else None)
        )
        try:
            tool_call_id, action_name, arguments = _parse_tool_call(tool_call)
        except (ValueError, json.JSONDecodeError, TypeError) as e:
            logger.warning("chat_with_agent: invalid tool_call payload: %s", e)
            return ChatMessage(
                role="tool",
                tool_call_id=fallback_tool_call_id,
                name="invalid_tool_call",
                content=json.dumps({"error": f"Invalid tool call: {e}"}, ensure_ascii=False),
            )
        logger.info(
            "chat_with_agent: executing tool name=%r tool_call_id=%r",
            action_name,
            tool_call_id,
        )
        try:
            result = await self._execute_action.execute_among_integrations(
                integrations,
                action_name,
                arguments,
            )
            content = json.dumps(result, ensure_ascii=False)
        except ActionNotFoundError as e:
            logger.warning("chat_with_agent: action not found: %s", e)
            content = json.dumps({"error": str(e)}, ensure_ascii=False)
        except IntegrationCallError as e:
            logger.warning("chat_with_agent: integration call failed: %s", e)
            content = json.dumps({"error": str(e)}, ensure_ascii=False)
        except Exception as e:  # noqa: BLE001 — сообщаем модели о любой неожиданной ошибке шага
            logger.exception("chat_with_agent: unexpected error running tool %r", action_name)
            content = json.dumps({"error": str(e)}, ensure_ascii=False)
        return ChatMessage(
            role="tool",
            tool_call_id=tool_call_id,
            name=action_name,
            content=content,
        )


def _parse_tool_call(tool_call: dict[str, Any]) -> tuple[str | None, str, dict[str, Any]]:
    """Извлечь id вызова, имя функции и аргументы из одного элемента ``tool_calls``."""
    tool_call_id = tool_call.get("id")
    if tool_call_id is not None and not isinstance(tool_call_id, str):
        tool_call_id = str(tool_call_id)
    fn = tool_call.get("function")
    if not isinstance(fn, dict):
        raise ValueError("tool_call.function must be a dict")
    name = fn.get("name")
    if not isinstance(name, str) or not name:
        raise ValueError("tool_call.function.name must be a non-empty string")
    raw_args = fn.get("arguments")
    if raw_args is None or raw_args == "":
        arguments: dict[str, Any] = {}
    elif isinstance(raw_args, dict):
        arguments = raw_args
    elif isinstance(raw_args, str):
        arguments = json.loads(raw_args)
    else:
        raise ValueError("tool_call.function.arguments must be str, dict, or empty")
    return tool_call_id, name, arguments
