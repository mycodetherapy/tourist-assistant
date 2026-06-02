#!/usr/bin/env python3
"""
Smoke-тест роутинга LLM (RU vs INTL).

Запуск из корня репозитория:
  python3 scripts/test_llm_routing.py
  python3 scripts/test_llm_routing.py --ru-only
  python3 scripts/test_llm_routing.py --intl-only
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from langchain_core.messages import HumanMessage

from agents.llm import _get_llm_cached, _pick_model_and_base_url, get_llm, infer_llm_region


def _mask_secret(value: str | None) -> str:
    if not value:
        return "(не задан)"
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}…{value[-4:]}"


def _check_keys(region: str) -> list[str]:
    issues: list[str] = []
    if region == "ru":
        if not (
            os.getenv("YANDEX_API_KEY")
            or os.getenv("YC_API_KEY")
            or os.getenv("OPENAI_API_KEY")
        ):
            issues.append("нет ключа: задайте YANDEX_API_KEY (или YC_API_KEY / OPENAI_API_KEY)")
    elif not os.getenv("OPENAI_API_KEY"):
        issues.append("нет OPENAI_API_KEY для ProxyAPI (intl)")
    return issues


def _probe(region: str, *, city: str) -> bool:
    inferred = infer_llm_region(city)
    model, base_url = _pick_model_and_base_url(region=region)
    print(f"\n=== region={region} (город «{city}» → infer={inferred}) ===")
    print(f"  model:    {model}")
    print(f"  base_url: {base_url}")

    key_issues = _check_keys(region)
    if key_issues:
        for issue in key_issues:
            print(f"  SKIP: {issue}")
        return False

    if region == "ru":
        key = os.getenv("YANDEX_API_KEY") or os.getenv("YC_API_KEY") or os.getenv("OPENAI_API_KEY")
        print(f"  api_key:  {_mask_secret(key)} (Yandex/YC/OpenAI)")
    else:
        print(f"  api_key:  {_mask_secret(os.getenv('OPENAI_API_KEY'))} (ProxyAPI)")

    _get_llm_cached.cache_clear()
    llm = get_llm(city=city, llm_region=region)
    prompt = HumanMessage(content="Ответь одним словом: ОК")
    try:
        response = llm.invoke([prompt])
        text = getattr(response, "content", str(response))
        preview = str(text).replace("\n", " ")[:120]
        print(f"  OK: {preview}")
        return True
    except Exception as exc:
        print(f"  FAIL: {type(exc).__name__}: {exc}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-тест LLM RU/INTL")
    parser.add_argument("--ru-only", action="store_true")
    parser.add_argument("--intl-only", action="store_true")
    args = parser.parse_args()

    run_ru = not args.intl_only
    run_intl = not args.ru_only

    print("LLM routing smoke test")
    print(f"  LLM_REGION={os.getenv('LLM_REGION', 'auto')}")

    ok = True
    if run_ru:
        ok = _probe("ru", city="Санкт-Петербург") and ok
    if run_intl:
        ok = _probe("intl", city="Paris") and ok

    print("\nИтог:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
