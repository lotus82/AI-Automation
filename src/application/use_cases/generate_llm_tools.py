"""Преобразование доменных действий интеграций в схемы инструментов OpenAI (function calling)."""

from __future__ import annotations

from typing import Any

from src.domain.entities.integration import (
    ActionParameter,
    ActionParamType,
    Integration,
    IntegrationAction,
)

# Соответствие доменных типов подмножеству JSON Schema для Chat Completions `tools`.
_PARAM_TYPE_TO_JSON_SCHEMA: dict[ActionParamType, str] = {
    ActionParamType.STRING: "string",
    ActionParamType.NUMBER: "number",
    ActionParamType.BOOLEAN: "boolean",
    ActionParamType.OBJECT: "object",
    ActionParamType.ARRAY: "array",
}


def map_action_param_type_to_json_schema(param_type: ActionParamType) -> str:
    """Возвращает строку ``type`` для вложенной JSON Schema (properties)."""
    return _PARAM_TYPE_TO_JSON_SCHEMA[param_type]


def build_tool_parameters_schema(parameters: list[ActionParameter]) -> dict[str, Any]:
    """Собирает объект ``parameters`` для ``function``: ``type`` + ``properties`` + ``required``."""
    properties: dict[str, Any] = {}
    required: list[str] = []
    for p in parameters:
        prop: dict[str, Any] = {
            "type": map_action_param_type_to_json_schema(p.type),
            "description": p.description,
        }
        if p.type == ActionParamType.ARRAY:
            # Минимально валидная схема массива для строгих валидаторов JSON Schema.
            prop["items"] = {"type": "string"}
        if p.type == ActionParamType.OBJECT:
            prop["additionalProperties"] = True
        properties[p.name] = prop
        if p.required:
            required.append(p.name)
    return {
        "type": "object",
        "properties": properties,
        "required": required,
    }


def integration_action_to_openai_tool(action: IntegrationAction) -> dict[str, Any]:
    """Один элемент списка ``tools`` в формате OpenAI (``type: function``)."""
    return {
        "type": "function",
        "function": {
            "name": action.name,
            "description": action.description,
            "parameters": build_tool_parameters_schema(list(action.parameters)),
        },
    }


class GenerateLLMToolsUseCase:
    """Строит список описаний function-tools по всем интеграциям (только ``is_llm_tool``).

    Имена инструментов — ``action.name``; при коллизиях между интеграциями вызывающий код
    должен обеспечивать уникальность (или позже добавить префикс по ``integration.name``).
    """

    def execute(self, integrations: list[Integration]) -> list[dict[str, Any]]:
        tools: list[dict[str, Any]] = []
        for integration in integrations:
            for action in integration.actions:
                if not action.is_llm_tool:
                    continue
                tools.append(integration_action_to_openai_tool(action))
        return tools
