"""LLM через ProxyAPI: planner с tool_calls, finalize со structured output."""

from __future__ import annotations

import os

from langchain_openai import ChatOpenAI

from config import settings
from models.schemas import FinalProgram
from search.tools import TOOLS

llm = ChatOpenAI(
    model=settings.LLM_MODEL,
    temperature=settings.LLM_TEMPERATURE,
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("PROXY_BASE_URL", settings.DEFAULT_PROXY_BASE_URL),
)

llm_with_tools = llm.bind_tools(TOOLS)
llm_final = llm.with_structured_output(FinalProgram, method="json_schema")

__all__ = ["llm", "llm_final", "llm_with_tools"]
