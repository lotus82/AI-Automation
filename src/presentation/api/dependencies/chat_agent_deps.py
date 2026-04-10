"""Зависимости для агента с инструментами (интеграции + OpenAI)."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException

from src.api.dependencies import SettingsDep
from src.application.use_cases.chat_with_agent import ChatWithAgentUseCase
from src.application.use_cases.generate_llm_tools import GenerateLLMToolsUseCase
from src.infrastructure.providers.openai_llm_provider import OpenAILLMProvider

from .integration_deps import ExecuteActionUseCaseDep, IntegrationRepositoryDep


def get_openai_llm_provider(settings: SettingsDep) -> OpenAILLMProvider:
    key = (settings.openai_api_key or "").strip()
    if not key:
        raise HTTPException(
            status_code=503,
            detail="Агентский чат недоступен: задайте OPENAI_API_KEY.",
        )
    return OpenAILLMProvider(api_key=key, model_name=settings.openai_agent_model)


def get_chat_with_agent_use_case(
    llm: Annotated[OpenAILLMProvider, Depends(get_openai_llm_provider)],
    repo: IntegrationRepositoryDep,
    execute_uc: ExecuteActionUseCaseDep,
) -> ChatWithAgentUseCase:
    return ChatWithAgentUseCase(
        llm,
        repo,
        GenerateLLMToolsUseCase(),
        execute_uc,
    )


OpenAILLMProviderDep = Annotated[OpenAILLMProvider, Depends(get_openai_llm_provider)]
ChatWithAgentUseCaseDep = Annotated[ChatWithAgentUseCase, Depends(get_chat_with_agent_use_case)]
