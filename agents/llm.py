"""LLM через OpenRouter: planner с tool_calls, finalize со structured output."""

from __future__ import annotations

import os
from functools import lru_cache

from langchain_openai import ChatOpenAI

from agents.llm_context import LlmConfig, get_current_llm_config
from config.settings import (
    LLM_MODEL,
    LLM_TEMPERATURE,
    get_llm_api_key,
    get_llm_base_url,
    get_llm_extra_body,
)
from models.schemas import RoutesDraft
from search.tools import TOOLS


def _config_from_env() -> LlmConfig:
    return LlmConfig(
        api_key=get_llm_api_key(),
        base_url=get_llm_base_url(),
        model=os.getenv("LLM_MODEL", LLM_MODEL),
    )


def _resolve_config() -> LlmConfig:
    try:
        return get_current_llm_config()
    except RuntimeError:
        return _config_from_env()


def _build_llm(config: LlmConfig) -> ChatOpenAI:
    extra: dict[str, object] = {
        "default_headers": {
            "HTTP-Referer": "https://github.com/tourist-assistant",
            "X-OpenRouter-Title": "tourist-assistant",
        },
    }
    extra_body = get_llm_extra_body()
    if extra_body:
        extra["extra_body"] = extra_body
    return ChatOpenAI(
        model=config.model,
        temperature=LLM_TEMPERATURE,
        api_key=config.api_key,
        base_url=config.base_url,
        **extra,
    )


@lru_cache(maxsize=8)
def _get_llm_cached(api_key: str, base_url: str, model: str) -> ChatOpenAI:
    return _build_llm(LlmConfig(api_key=api_key, base_url=base_url, model=model))


def get_llm() -> ChatOpenAI:
    config = _resolve_config()
    return _get_llm_cached(config.api_key, config.base_url, config.model)


def get_llm_with_tools():
    return get_llm().bind_tools(TOOLS)


def get_llm_final():
    return (
        get_llm()
        .bind(max_tokens=10_240)
        .with_structured_output(RoutesDraft, method="json_schema")
    )


def clear_llm_cache() -> None:
    _get_llm_cached.cache_clear()


__all__ = [
    "clear_llm_cache",
    "get_llm",
    "get_llm_final",
    "get_llm_with_tools",
]
