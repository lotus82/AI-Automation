"""Маршруты текстового чата с RAG."""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, status

from src.api.dependencies import ProcessTextMessageUseCaseDep
from src.api.schemas.chat import (
    ChatFinalizeRequest,
    ChatFinalizeResponse,
    ChatTextRequest,
    ChatTextResponse,
)

router = APIRouter()


@router.post(
    "/text",
    response_model=ChatTextResponse,
    status_code=status.HTTP_200_OK,
    summary="Текстовый запрос с RAG",
)
async def chat_text(
    body: ChatTextRequest,
    use_case: ProcessTextMessageUseCaseDep,
) -> ChatTextResponse:
    """Принимает сообщение, подмешивает историю из Redis, RAG и возвращает ответ LLM."""
    session_id = body.session_id or uuid4()
    reply = await use_case.execute(body.message, str(session_id))
    return ChatTextResponse(reply=reply, session_id=session_id)


@router.post(
    "/finalize",
    response_model=ChatFinalizeResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Завершить текстовую сессию и запустить ОКК",
)
async def chat_finalize(body: ChatFinalizeRequest) -> ChatFinalizeResponse:
    """Ставит в очередь Celery задачу анализа диалога (после окончания переписки в чате)."""
    from src.workers.tasks import analyze_conversation_task

    sid = str(body.session_id)
    analyze_conversation_task.delay(sid)
    return ChatFinalizeResponse(status="queued", session_id=body.session_id)
