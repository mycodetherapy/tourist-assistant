"""Уровень 3: LLM-as-judge (опционально, --with-llm)."""

from __future__ import annotations

import json
import os
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field


class JudgeVerdict(BaseModel):
    """Вердикт судьи по качеству программы."""

    prices_ok: bool = Field(..., description="Цены только со ссылками")
    city_ok: bool = Field(..., description="Город не перепутан")
    score: int = Field(..., ge=1, le=5, description="Общая оценка 1-5")
    comment: str = Field(default="", description="Краткий комментарий")


def run_llm_judge(
    program: dict[str, Any],
    *,
    city: str,
    origin_city: str,
) -> tuple[JudgeVerdict | None, str | None]:
    """Вызов LLM-судьи; при ошибке (нет ключа) возвращает (None, error)."""
    if not os.getenv("OPENAI_API_KEY"):
        return None, "OPENAI_API_KEY не задан"

    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("PROXY_BASE_URL", "https://openai.api.proxyapi.ru/v1"),
    )
    judge = llm.with_structured_output(JudgeVerdict, method="json_schema")
    system = SystemMessage(
        content=(
            "Ты — судья качества туристической программы. "
            "Проверь: цены только со ссылками или «уточните на сайте»; "
            f"город поездки {city}, вылет из {origin_city} — не перепутаны."
        )
    )
    human = HumanMessage(content=json.dumps(program, ensure_ascii=False))
    try:
        verdict: JudgeVerdict = judge.invoke([system, human])
        return verdict, None
    except Exception as exc:
        return None, str(exc)
