"""Юнит-тесты для ``GenerateLLMToolsUseCase`` (stdlib ``unittest``)."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from uuid import uuid4

from pydantic import HttpUrl, SecretStr

from src.application.use_cases.generate_llm_tools import (
    GenerateLLMToolsUseCase,
    build_tool_parameters_schema,
    integration_action_to_openai_tool,
    map_action_param_type_to_json_schema,
)
from src.domain.entities.integration import (
    ActionParameter,
    ActionParamType,
    ApiKeyAuthConfig,
    Integration,
    IntegrationAction,
)


class TestMapActionParamType(unittest.TestCase):
    def test_all_domain_types_map(self) -> None:
        self.assertEqual(map_action_param_type_to_json_schema(ActionParamType.STRING), "string")
        self.assertEqual(map_action_param_type_to_json_schema(ActionParamType.NUMBER), "number")
        self.assertEqual(map_action_param_type_to_json_schema(ActionParamType.BOOLEAN), "boolean")
        self.assertEqual(map_action_param_type_to_json_schema(ActionParamType.OBJECT), "object")
        self.assertEqual(map_action_param_type_to_json_schema(ActionParamType.ARRAY), "array")


class TestBuildToolParametersSchema(unittest.TestCase):
    def test_empty_parameters(self) -> None:
        schema = build_tool_parameters_schema([])
        self.assertEqual(schema["type"], "object")
        self.assertEqual(schema["properties"], {})
        self.assertEqual(schema["required"], [])

    def test_required_and_optional(self) -> None:
        params = [
            ActionParameter(
                name="order_id",
                type=ActionParamType.STRING,
                description="Идентификатор заказа",
                required=True,
            ),
            ActionParameter(
                name="limit",
                type=ActionParamType.NUMBER,
                description="Лимит",
                required=False,
            ),
        ]
        schema = build_tool_parameters_schema(params)
        self.assertIn("order_id", schema["properties"])
        self.assertIn("limit", schema["properties"])
        self.assertEqual(schema["properties"]["order_id"]["type"], "string")
        self.assertEqual(schema["required"], ["order_id"])


class TestIntegrationActionToOpenaiTool(unittest.TestCase):
    def test_shape(self) -> None:
        action = IntegrationAction(
            name="get_order",
            description="Получить заказ",
            method="GET",
            path="/orders/{order_id}",
            parameters=[
                ActionParameter(
                    name="order_id",
                    type=ActionParamType.STRING,
                    description="ID",
                    required=True,
                ),
            ],
            is_llm_tool=True,
        )
        tool = integration_action_to_openai_tool(action)
        self.assertEqual(tool["type"], "function")
        self.assertEqual(tool["function"]["name"], "get_order")
        self.assertEqual(tool["function"]["description"], "Получить заказ")
        self.assertEqual(tool["function"]["parameters"]["type"], "object")
        self.assertEqual(list(tool["function"]["parameters"]["required"]), ["order_id"])


class TestGenerateLLMToolsUseCase(unittest.TestCase):
    def _sample_integration(self, *, with_internal: bool) -> Integration:
        now = datetime.now(timezone.utc)
        uid = uuid4()
        actions = [
            IntegrationAction(
                name="public_tool",
                description="Виден LLM",
                method="GET",
                path="/x",
                parameters=[],
                is_llm_tool=True,
            ),
        ]
        if with_internal:
            actions.append(
                IntegrationAction(
                    name="internal_only",
                    description="Только Celery",
                    method="POST",
                    path="/internal",
                    parameters=[],
                    is_llm_tool=False,
                ),
            )
        return Integration(
            id=uid,
            name="Demo",
            base_url=HttpUrl("https://api.example.com"),
            auth=ApiKeyAuthConfig(header_name="X-Key", header_value=SecretStr("k")),
            actions=actions,
            webhooks=[],
            created_at=now,
            updated_at=now,
        )

    def test_filters_non_llm_tools(self) -> None:
        uc = GenerateLLMToolsUseCase()
        out = uc.execute([self._sample_integration(with_internal=True)])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["function"]["name"], "public_tool")

    def test_multiple_integrations(self) -> None:
        uc = GenerateLLMToolsUseCase()
        out = uc.execute(
            [
                self._sample_integration(with_internal=False),
                self._sample_integration(with_internal=False),
            ]
        )
        self.assertEqual(len(out), 2)
        self.assertTrue(all(t["function"]["name"] == "public_tool" for t in out))


if __name__ == "__main__":
    unittest.main()
