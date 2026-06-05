#!/usr/bin/env python3
"""
Smoke-тест LLM (один endpoint через LLM_API_KEY).

Запуск из корня репозитория:
  python3 scripts/test_llm.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from langchain_core.messages import HumanMessage

from agents.llm import _get_llm_cached, get_llm
from config.settings import LLM_MODEL, get_llm_api_key, get_llm_base_url


def _mask_secret(value: str | None) -> str:
    if not value:
        return "(не задан)"
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}…{value[-4:]}"


def main() -> int:
    model = os.getenv("LLM_MODEL", LLM_MODEL)
    base_url = get_llm_base_url()
    api_key = get_llm_api_key()

    print("LLM smoke test")
    print(f"  model:    {model}")
    print(f"  base_url: {base_url}")
    print(f"  api_key:  {_mask_secret(api_key)}")

    if not api_key:
        print("  SKIP: задайте LLM_API_KEY в .env")
        return 1

    _get_llm_cached.cache_clear()
    llm = get_llm()
    prompt = HumanMessage(content="Ответь одним словом: ОК")
    try:
        response = llm.invoke([prompt])
        text = getattr(response, "content", str(response))
        preview = str(text).replace("\n", " ")[:120]
        print(f"  OK: {preview}")
        return 0
    except Exception as exc:
        print(f"  FAIL: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
