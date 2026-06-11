"""Контекст LLM для BYOK: ключ пользователя на время прогона графа."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Iterator

_llm_config: ContextVar["LlmConfig | None"] = ContextVar("llm_config", default=None)


@dataclass(frozen=True)
class LlmConfig:
    api_key: str
    base_url: str
    model: str


def get_current_llm_config() -> LlmConfig:
    config = _llm_config.get()
    if config is None:
        raise RuntimeError(
            "LlmConfig не задан в контексте. Оберните вызов в run_with_llm_config()."
        )
    return config


@contextmanager
def run_with_llm_config(config: LlmConfig) -> Iterator[None]:
    token = _llm_config.set(config)
    try:
        yield
    finally:
        _llm_config.reset(token)
