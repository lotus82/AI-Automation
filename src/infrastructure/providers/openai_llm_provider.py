"""Реализация ``ILLMProvider`` через официальный ``AsyncOpenAI`` (Chat Completions)."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator, Sequence
from typing import Any

from openai import APIError, APIConnectionError, APITimeoutError, AsyncOpenAI, AuthenticationError, RateLimitError

from src.application.interfaces.providers.llm_provider import ChatMessage, ILLMProvider, LLMProviderError

logger = logging.getLogger(__name__)


class OpenAILLMProviderError(LLMProviderError):
    """Сбой вызова OpenAI Chat Completions (сеть, квота, ключ, ответ API)."""


def _tool_calls_to_raw(tool_calls: Sequence[Any] | None) -> list[dict[str, Any]] | None:
    if not tool_calls:
        return None
    raw: list[dict[str, Any]] = []
    for tc in tool_calls:
        if hasattr(tc, "model_dump"):
            raw.append(tc.model_dump())
            continue
        fn = getattr(tc, "function", None)
        raw.append(
            {
                "id": getattr(tc, "id", None),
                "type": getattr(tc, "type", "function") or "function",
                "function": {
                    "name": getattr(fn, "name", "") if fn is not None else "",
                    "arguments": getattr(fn, "arguments", "") if fn is not None else "",
                },
            }
        )
    return raw


def chat_messages_to_openai_params(messages: list[ChatMessage]) -> list[dict[str, Any]]:
    """Маппинг доменных сообщений в формат ``chat.completions.create``."""
    rows: list[dict[str, Any]] = []
    for m in messages:
        if m.role == "tool":
            row: dict[str, Any] = {
                "role": "tool",
                "content": m.content if m.content is not None else "",
            }
            if m.tool_call_id:
                row["tool_call_id"] = m.tool_call_id
            if m.name:
                row["name"] = m.name
            rows.append(row)
            continue
        if m.role == "assistant" and m.tool_calls:
            row = {"role": "assistant", "tool_calls": m.tool_calls}
            row["content"] = m.content
            rows.append(row)
            continue
        rows.append({"role": m.role, "content": m.content if m.content is not None else ""})
    return rows


def _openai_message_to_chat_message(msg: Any) -> ChatMessage:
    tool_raw = _tool_calls_to_raw(getattr(msg, "tool_calls", None))
    return ChatMessage(
        role=getattr(msg, "role", "assistant") or "assistant",
        content=getattr(msg, "content", None),
        tool_calls=tool_raw,
    )


class OpenAILLMProvider(ILLMProvider):
    """Небуферизованный шаг диалога (``stream=False``) и отдельный поток для финального ответа."""

    def __init__(
        self,
        *,
        api_key: str,
        model_name: str,
        timeout: float | None = 120.0,
    ) -> None:
        if not (api_key or "").strip():
            raise ValueError("api_key must be non-empty for OpenAILLMProvider")
        self._model_name = model_name
        self._client = AsyncOpenAI(api_key=api_key.strip(), timeout=timeout)

    @property
    def model_name(self) -> str:
        return self._model_name

    def _map_client_error(self, exc: Exception) -> OpenAILLMProviderError:
        if isinstance(exc, AuthenticationError):
            return OpenAILLMProviderError("OpenAI: неверный или отсутствующий API-ключ.")
        if isinstance(exc, RateLimitError):
            return OpenAILLMProviderError("OpenAI: превышен лимит запросов (rate limit).")
        if isinstance(exc, (APIConnectionError, APITimeoutError)):
            return OpenAILLMProviderError(f"OpenAI: сетевая ошибка или таймаут: {exc}")
        if isinstance(exc, APIError):
            return OpenAILLMProviderError(f"OpenAI API: {exc}")
        return OpenAILLMProviderError(f"OpenAI: {exc}")

    async def generate_response(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
    ) -> ChatMessage:
        payload = chat_messages_to_openai_params(messages)
        kwargs: dict[str, Any] = {
            "model": self._model_name,
            "messages": payload,
            "stream": False,
        }
        if tools:
            kwargs["tools"] = tools
        try:
            completion = await self._client.chat.completions.create(**kwargs)
        except (APIError, APIConnectionError, APITimeoutError, AuthenticationError, RateLimitError) as e:
            logger.warning("OpenAILLMProvider.generate_response failed: %s", e)
            mapped = self._map_client_error(e)
            raise mapped from e
        except Exception as e:
            logger.exception("OpenAILLMProvider.generate_response unexpected error")
            raise OpenAILLMProviderError(str(e)) from e

        choice = completion.choices[0]
        msg = choice.message
        return _openai_message_to_chat_message(msg)

    async def stream_response(self, messages: list[ChatMessage]) -> AsyncGenerator[str, None]:
        """Потоковая генерация финального ответа без tools (``stream=True``)."""
        payload = chat_messages_to_openai_params(messages)
        try:
            stream = await self._client.chat.completions.create(
                model=self._model_name,
                messages=payload,
                stream=True,
            )
        except (APIError, APIConnectionError, APITimeoutError, AuthenticationError, RateLimitError) as e:
            logger.warning("OpenAILLMProvider.stream_response (create) failed: %s", e)
            mapped = self._map_client_error(e)
            raise mapped from e
        except Exception as e:
            logger.exception("OpenAILLMProvider.stream_response unexpected error on create")
            raise OpenAILLMProviderError(str(e)) from e

        try:
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta is None:
                    continue
                content = getattr(delta, "content", None)
                if content:
                    yield content
        except (APIError, APIConnectionError, APITimeoutError, AuthenticationError, RateLimitError) as e:
            logger.warning("OpenAILLMProvider.stream_response (iter) failed: %s", e)
            mapped = self._map_client_error(e)
            raise mapped from e
        except Exception as e:
            logger.exception("OpenAILLMProvider.stream_response unexpected error while streaming")
            raise OpenAILLMProviderError(str(e)) from e
