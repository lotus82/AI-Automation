"""SSE-стриминг ответа агента с инструментами (интеграции), POST ``/api/v1/chat/stream``."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException

from src.api.client_timezone import ClientTimezoneIdDep
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.application.interfaces.providers.llm_provider import ChatMessage, LLMProviderError
from src.domain.exceptions.integration_exceptions import IntegrationNotFoundError

from ..dependencies.chat_agent_deps import ChatWithAgentUseCaseDep, OpenAILLMProviderDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/chat", tags=["Agent Chat"])


class ChatRequest(BaseModel):
    """Тело запроса на потоковый ответ агента."""

    message: str = Field(min_length=1, description="Текущее сообщение пользователя.")
    history: list[dict[str, Any]] | None = Field(
        default=None,
        description="Прошлые сообщения в формате полей ChatMessage (role, content, ...).",
    )
    integration_ids: list[UUID] = Field(
        default_factory=list,
        description="Интеграции, чьи LLM-tools доступны в этом запросе.",
    )
    system_prompt: str | None = Field(
        default=None,
        description="Системный промпт; если не задан — используется значение по умолчанию.",
    )


_DEFAULT_SYSTEM = (
    "You are a helpful assistant. Use the provided tools when they help answer the user. "
    "Respond concisely in the same language as the user when possible."
)


def _history_to_chat_messages(history: list[dict[str, Any]] | None) -> list[ChatMessage]:
    if not history:
        return []
    out: list[ChatMessage] = []
    for row in history:
        if not isinstance(row, dict):
            continue
        data = {k: v for k, v in row.items() if k in ("role", "content", "name", "tool_call_id", "tool_calls")}
        if "role" not in data:
            continue
        try:
            out.append(ChatMessage.model_validate(data))
        except Exception:
            logger.debug("chat.stream: skip invalid history row: %r", row, exc_info=True)
    return out


@router.post("/stream")
async def stream_agent_chat(
    body: ChatRequest,
    use_case: ChatWithAgentUseCaseDep,
    llm: OpenAILLMProviderDep,
    client_tz: ClientTimezoneIdDep,
) -> StreamingResponse:
    """Сначала цикл tool calls (нестриминг), затем финальный ответ через SSE ``data: …\\n\\n``."""
    system_prompt = (body.system_prompt or "").strip() or _DEFAULT_SYSTEM
    chat_history = _history_to_chat_messages(body.history)

    try:
        messages = await use_case.execute_messages(
            system_prompt,
            chat_history,
            body.message.strip(),
            body.integration_ids,
            client_timezone_id=client_tz,
        )
    except IntegrationNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except LLMProviderError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except Exception as e:
        logger.exception("chat.stream: execute_messages failed")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка при подготовке ответа.") from e

    async def sse_body() -> AsyncIterator[bytes]:
        try:
            async for chunk in llm.stream_response(messages):
                line = f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                yield line.encode("utf-8")
        except LLMProviderError as e:
            logger.warning("chat.stream: OpenAI stream failed: %s", e)
            err_line = f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
            yield err_line.encode("utf-8")
        except Exception as e:
            logger.exception("chat.stream: unexpected stream error")
            err_line = f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
            yield err_line.encode("utf-8")

    return StreamingResponse(
        sse_body(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
