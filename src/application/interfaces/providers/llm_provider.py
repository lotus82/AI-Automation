"""Порт вызова LLM (без привязки к OpenAI/Anthropic SDK)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class LLMProviderError(RuntimeError):
    """Сбой вызова LLM (сеть, квота, неверный ключ, ответ API)."""


class ChatMessage(BaseModel):
    """Сообщение диалога для провайдера LLM и цикла агента."""

    model_config = ConfigDict(extra="forbid")

    role: str = Field(
        description='Роль: "system", "user", "assistant", "tool".',
    )
    content: str | None = Field(default=None, description="Текст сообщения или JSON-ответ инструмента.")
    name: str | None = Field(
        default=None,
        description="Для role=tool: имя вызванной функции/действия.",
    )
    tool_call_id: str | None = Field(
        default=None,
        description="Идентификатор вызова инструмента (связка с assistant.tool_calls).",
    )
    tool_calls: list[dict[str, Any]] | None = Field(
        default=None,
        description="Сырые tool_calls от ассистента (например формат OpenAI Chat Completions).",
    )


class ILLMProvider(ABC):
    """Абстракция модели: один шаг генерации с опциональным function calling."""

    @abstractmethod
    async def generate_response(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
    ) -> ChatMessage:
        """Вернуть следующее сообщение ассистента (возможно с ``tool_calls``)."""
