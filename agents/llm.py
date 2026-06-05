"""LLM через OpenRouter: planner с tool_calls, finalize со structured output."""

from __future__ import annotations

import os
from functools import lru_cache

from langchain_openai import ChatOpenAI

from config.settings import (
    LLM_MODEL,
    LLM_TEMPERATURE,
    get_llm_api_key,
    get_llm_base_url,
    get_llm_extra_body,
)
from models.schemas import ProgramDraft
from search.tools import TOOLS


@lru_cache(maxsize=1)
def _get_llm_cached() -> ChatOpenAI:
    # Единая модель: LLM_API_KEY + LLM_BASE_URL + LLM_MODEL (OpenRouter по умолчанию).
    model = os.getenv("LLM_MODEL", LLM_MODEL)
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
        model=model,
        temperature=LLM_TEMPERATURE,
        api_key=get_llm_api_key(),
        base_url=get_llm_base_url(),
        **extra,
    )


def get_llm() -> ChatOpenAI:
    return _get_llm_cached()


def get_llm_with_tools():
    return get_llm().bind_tools(TOOLS)


def get_llm_final():
    # Билеты не в схеме LLM — иначе json_schema ломается на больших tool JSON.
    return (
        get_llm()
        .bind(max_tokens=12_288)
        .with_structured_output(ProgramDraft, method="json_schema")
    )


__all__ = [
    "get_llm",
    "get_llm_final",
    "get_llm_with_tools",
]
