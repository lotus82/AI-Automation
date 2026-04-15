"""Маршруты текстового чата с RAG."""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, status

from src.api.dependencies import (
    AsyncSessionDep,
    RedisDep,
    SettingsDep,
    build_process_text_message_use_case,
    get_process_text_message_use_case,
)
from src.api.dependencies_portal import get_portal_user
from src.api.org_scope import resolve_organization_scope
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
    request: Request,
    session: AsyncSessionDep,
    redis: RedisDep,
    settings: SettingsDep,
) -> ChatTextResponse:
    """Принимает сообщение, подмешивает историю из Redis, RAG и возвращает ответ LLM.

    С JWT портала: для пользователя с организацией — всегда его (или явный ``organization_id`` у супер-админа).
    Без JWT: только глобальные настройки; поле ``organization_id`` в теле запрещено.
    """
    session_id = body.session_id or uuid4()
    if getattr(request.state, "portal_token_payload", None):
        user = await get_portal_user(request, session)
        scope = resolve_organization_scope(user, body.organization_id)
        use_case = build_process_text_message_use_case(session, redis, settings, organization_id=scope)
    else:
        if body.organization_id is not None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Для запросов с organization_id нужна авторизация портала (Authorization: Bearer …)",
            )
        use_case = get_process_text_message_use_case(session, redis, settings)
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
