"""Юнит-тесты для ``ChatWithAgentUseCase``."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from pydantic import HttpUrl, SecretStr

from src.application.interfaces.providers.llm_provider import ChatMessage, ILLMProvider
from src.application.use_cases.chat_with_agent import ChatWithAgentUseCase
from src.application.use_cases.execute_action import ExecuteActionUseCase
from src.application.use_cases.generate_llm_tools import GenerateLLMToolsUseCase
from src.domain.entities.integration import (
    ActionParameter,
    ActionParamType,
    ApiKeyAuthConfig,
    Integration,
    IntegrationAction,
)
from src.domain.exceptions.integration_exceptions import IntegrationCallError


def _sample_integration(integration_id, action_name: str = "ping") -> Integration:
    now = datetime.now(timezone.utc)
    return Integration(
        id=integration_id,
        name="Test API",
        base_url=HttpUrl("https://example.com"),
        auth=ApiKeyAuthConfig(header_name="X-Key", header_value=SecretStr("secret")),
        actions=[
            IntegrationAction(
                name=action_name,
                description="Ping",
                method="GET",
                path="/ping",
                parameters=[
                    ActionParameter(
                        name="q",
                        type=ActionParamType.STRING,
                        description="q",
                        required=False,
                    ),
                ],
                is_llm_tool=True,
            ),
        ],
        webhooks=[],
        created_at=now,
        updated_at=now,
    )


class _FakeLLM(ILLMProvider):
    def __init__(self, responses: list[ChatMessage]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[list[ChatMessage], list[dict[str, Any]] | None]] = []

    async def generate_response(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
    ) -> ChatMessage:
        self.calls.append((messages, tools))
        if not self._responses:
            return ChatMessage(role="assistant", content="fallback")
        return self._responses.pop(0)


class TestChatWithAgentUseCase(unittest.IsolatedAsyncioTestCase):
    async def test_final_answer_without_tools(self) -> None:
        iid = uuid4()
        integration = _sample_integration(iid)
        repo = MagicMock()
        repo.get_by_id = AsyncMock(return_value=integration)
        llm = _FakeLLM([ChatMessage(role="assistant", content="Hello", tool_calls=None)])
        uc = ChatWithAgentUseCase(
            llm,
            repo,
            GenerateLLMToolsUseCase(),
            ExecuteActionUseCase(repo, MagicMock()),
            max_iterations=5,
        )
        out = await uc.execute("You are helpful.", [], "Hi", [iid])
        self.assertEqual(out, "Hello")
        repo.get_by_id.assert_awaited_once_with(iid)

    async def test_execute_messages_no_tools_excludes_assistant(self) -> None:
        iid = uuid4()
        integration = _sample_integration(iid)
        repo = MagicMock()
        repo.get_by_id = AsyncMock(return_value=integration)
        llm = _FakeLLM([ChatMessage(role="assistant", content="Hello", tool_calls=None)])
        uc = ChatWithAgentUseCase(
            llm,
            repo,
            GenerateLLMToolsUseCase(),
            ExecuteActionUseCase(repo, MagicMock()),
        )
        msgs = await uc.execute_messages("You are helpful.", [], "Hi", [iid])
        self.assertEqual([m.role for m in msgs], ["system", "user"])
        self.assertFalse(any(m.role == "assistant" for m in msgs))

    async def test_tool_round_then_answer(self) -> None:
        iid = uuid4()
        integration = _sample_integration(iid, "get_status")
        repo = MagicMock()
        repo.get_by_id = AsyncMock(return_value=integration)
        tool_calls = [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "get_status", "arguments": '{"q": "x"}'},
            },
        ]
        llm = _FakeLLM(
            [
                ChatMessage(role="assistant", content=None, tool_calls=tool_calls),
                ChatMessage(role="assistant", content="Done", tool_calls=None),
            ],
        )
        exec_uc = ExecuteActionUseCase(repo, MagicMock())
        exec_uc.execute_among_integrations = AsyncMock(return_value={"ok": True})
        uc = ChatWithAgentUseCase(
            llm,
            repo,
            GenerateLLMToolsUseCase(),
            exec_uc,
            max_iterations=5,
        )
        out = await uc.execute("sys", [], "go", [iid])
        self.assertEqual(out, "Done")
        exec_uc.execute_among_integrations.assert_awaited_once()
        args, _kw = exec_uc.execute_among_integrations.await_args
        self.assertEqual(args[1], "get_status")
        self.assertEqual(args[2], {"q": "x"})

    async def test_integration_error_becomes_tool_json(self) -> None:
        iid = uuid4()
        integration = _sample_integration(iid, "fail_action")
        repo = MagicMock()
        repo.get_by_id = AsyncMock(return_value=integration)
        tool_calls = [
            {
                "id": "c2",
                "type": "function",
                "function": {"name": "fail_action", "arguments": "{}"},
            },
        ]
        llm = _FakeLLM(
            [
                ChatMessage(role="assistant", content=None, tool_calls=tool_calls),
                ChatMessage(role="assistant", content="Recovered", tool_calls=None),
            ],
        )
        exec_uc = ExecuteActionUseCase(repo, MagicMock())
        exec_uc.execute_among_integrations = AsyncMock(
            side_effect=IntegrationCallError("boom", status_code=500),
        )
        uc = ChatWithAgentUseCase(llm, repo, GenerateLLMToolsUseCase(), exec_uc)
        out = await uc.execute("sys", [], "go", [iid])
        self.assertEqual(out, "Recovered")
        second_messages = llm.calls[1][0]
        tool_msgs = [m for m in second_messages if m.role == "tool"]
        self.assertTrue(any("boom" in (m.content or "") for m in tool_msgs))

    async def test_execute_messages_ends_with_tool_before_stream(self) -> None:
        iid = uuid4()
        integration = _sample_integration(iid, "get_status")
        repo = MagicMock()
        repo.get_by_id = AsyncMock(return_value=integration)
        tool_calls = [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "get_status", "arguments": "{}"},
            },
        ]
        llm = _FakeLLM(
            [
                ChatMessage(role="assistant", content=None, tool_calls=tool_calls),
                ChatMessage(role="assistant", content="Done", tool_calls=None),
            ],
        )
        exec_uc = ExecuteActionUseCase(repo, MagicMock())
        exec_uc.execute_among_integrations = AsyncMock(return_value={"ok": True})
        uc = ChatWithAgentUseCase(llm, repo, GenerateLLMToolsUseCase(), exec_uc)
        msgs = await uc.execute_messages("sys", [], "go", [iid])
        self.assertEqual(msgs[-1].role, "tool")
        self.assertFalse(any(m.content == "Done" for m in msgs))


if __name__ == "__main__":
    unittest.main()
