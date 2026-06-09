"""Разбор JSON-ответа инструмента для записи в tool_runs."""

from __future__ import annotations

import json
from typing import Any


def parse_tool_result(content: str) -> dict[str, Any]:
    """
    Извлекает метрики из payload инструмента (строка JSON или текст ошибки).
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return {
            "live_data": False,
            "results_count": 0,
            "raw_results_count": 0,
            "provider": None,
            "error": content[:500],
        }

    if not isinstance(data, dict):
        return {
            "live_data": False,
            "results_count": 0,
            "raw_results_count": 0,
            "provider": None,
            "error": "invalid payload",
        }

    if "error" in data and data.get("live_data") is False:
        return {
            "live_data": False,
            "results_count": 0,
            "raw_results_count": 0,
            "provider": data.get("search_provider"),
            "error": str(data.get("error", ""))[:500],
        }

    if data.get("category") == "route_materials":
        count = int(data.get("leisure_count", data.get("results_count", 0)))
        return {
            "live_data": bool(data.get("live_data", count > 0)),
            "results_count": count,
            "raw_results_count": count,
            "provider": str(data.get("provider") or "osm"),
            "error": data.get("error") or data.get("warning"),
        }

    if data.get("category") == "tickets" and data.get("schema_version") == "1":
        count = int(data.get("offers_count", data.get("results_count", 0)))
        provider = (
            "travelpayouts"
            if data.get("avia_api_status") == "ok"
            else "deep_links"
        )
        return {
            "live_data": bool(data.get("live_data", count > 0)),
            "results_count": count,
            "raw_results_count": count,
            "provider": provider,
            "error": data.get("error"),
        }

    # search_dining: вложенный поиск ресторанов
    if "search" in data and isinstance(data["search"], dict):
        nested = data["search"]
        if "restaurants" in nested:
            rest = nested.get("restaurants") or {}
            return {
                "live_data": bool(data.get("live_data", True)),
                "results_count": int(rest.get("results_count", 0)),
                "raw_results_count": int(rest.get("raw_results_count", 0)),
                "provider": rest.get("provider"),
                "error": None,
            }

    search_block = data.get("search")
    if isinstance(search_block, dict):
        provider = search_block.get("provider") or data.get("search_provider")
        results_count = int(
            data.get("results_count", search_block.get("results_count", 0))
        )
        raw_results_count = int(
            data.get("raw_results_count", search_block.get("raw_results_count", 0))
        )
    else:
        provider = data.get("search_provider")
        results_count = int(data.get("results_count", 0))
        raw_results_count = int(data.get("raw_results_count", 0))

    return {
        "live_data": bool(data.get("live_data", results_count > 0)),
        "results_count": results_count,
        "raw_results_count": raw_results_count,
        "provider": provider,
        "error": data.get("error"),
    }
