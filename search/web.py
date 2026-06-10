"""Веб-поиск живых данных: Tavily при наличии ключа, иначе ddgs (ru-ru)."""

from __future__ import annotations

import os
from typing import Any

import requests

from config import settings


def _city_aliases(city: str) -> list[str]:
    """Ключевые слова для проверки, что результат относится к нужному городу."""
    normalized = city.lower().strip()
    aliases = [normalized]
    if "санкт" in normalized or "петербург" in normalized:
        aliases.extend(
            [
                "санкт-петербург",
                "петербург",
                "питер",
                "спб",
                "petersburg",
                "saint-petersburg",
            ]
        )
    if normalized == "москва":
        aliases.extend(["москв", "moscow"])
    if "казан" in normalized:
        aliases.extend(["казан", "kazan"])
    return aliases


def _matches_city(blob: str, city_keys: list[str]) -> bool:
    """Проверяет, что сниппет относится к целевому городу."""
    if not city_keys:
        return True
    return any(alias in blob for alias in city_keys)


def _text_blob(item: dict[str, str | None]) -> str:
    return " ".join(
        filter(
            None,
            [
                (item.get("title") or "").lower(),
                (item.get("url") or "").lower(),
                (item.get("snippet") or "").lower(),
            ],
        )
    )


def _filter_results(
    results: list[dict[str, str | None]],
    kind: str,
    cities: list[str] | None = None,
) -> list[dict[str, str | None]]:
    """Оставляет результаты, подходящие под тип инструмента и (опционально) город."""
    rules = settings.SEARCH_FILTERS.get(kind, {})
    include_any = rules.get("include_any", ())
    exclude_any = rules.get("exclude_any", ())
    city_keys: list[str] = []
    for city in cities or []:
        if city:
            city_keys.extend(_city_aliases(city))

    filtered: list[dict[str, str | None]] = []
    for item in results:
        blob = _text_blob(item)
        if exclude_any and any(word in blob for word in exclude_any):
            continue
        if include_any and not any(word in blob for word in include_any):
            continue
        if kind in {"events", "restaurants", "landmarks"} and city_keys:
            target_city = next((c for c in (cities or []) if c), "")
            if target_city and not _matches_city(blob, _city_aliases(target_city)):
                continue
        filtered.append(item)
    return filtered


def _dedupe_results(results: list[dict[str, str | None]]) -> list[dict[str, str | None]]:
    """Убирает дубликаты по URL."""
    seen: set[str] = set()
    unique: list[dict[str, str | None]] = []
    for item in results:
        url = (item.get("url") or "").strip()
        key = url.lower() if url else (item.get("title") or "")
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def format_search_digest(
    results: list[dict[str, str | None]],
    *,
    kind: str = "general",
) -> str:
    """Текстовая сводка результатов — LLM легче использует её, чем сырой JSON."""
    if not results:
        return "Результаты поиска пусты."
    if kind == "events":
        from search.digest_format import format_events_digest

        return format_events_digest(results)
    from search.digest_format import sanitize_snippet

    lines: list[str] = []
    for index, item in enumerate(results, start=1):
        title = item.get("title") or "Без названия"
        url = item.get("url") or ""
        snippet = sanitize_snippet(str(item.get("snippet") or ""))
        block = f"{index}. {title}"
        if url:
            block += f"\n   Ссылка: {url}"
        if snippet:
            block += f"\n   {snippet}"
        lines.append(block)
    return "\n\n".join(lines)


def _search_via_tavily(query: str, api_key: str) -> dict[str, Any]:
    """Поиск через Tavily API (нужен TAVILY_API_KEY)."""
    response = requests.post(
        "https://api.tavily.com/search",
        json={
            "api_key": api_key,
            "query": query,
            "max_results": settings.MAX_SEARCH_RESULTS,
            "search_depth": "advanced",
            "include_answer": True,
        },
        timeout=settings.SEARCH_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    return {
        "provider": "tavily",
        "query": query,
        "answer": data.get("answer"),
        "results": [
            {
                "title": item.get("title"),
                "url": item.get("url"),
                "snippet": item.get("content"),
            }
            for item in data.get("results", [])
        ],
    }


def _collect_ddgs_items(
    ddgs_client: Any,
    query: str,
    max_results: int | None = None,
) -> list[dict[str, str | None]]:
    """Собирает результаты text-поиска из клиента DDGS."""
    limit = max_results or settings.MAX_SEARCH_RESULTS
    collected: list[dict[str, str | None]] = []
    for item in ddgs_client.text(
        query,
        region=settings.DDG_REGION,
        max_results=limit,
    ):
        collected.append(
            {
                "title": item.get("title"),
                "url": item.get("href"),
                "snippet": item.get("body"),
            }
        )
    return collected


def _search_via_ddgs_batch(
    queries: list[str],
    max_results: int | None = None,
) -> list[dict[str, str | None]]:
    """Один клиент ddgs на все запросы — меньше сбоев SSL и утечек сокетов."""
    try:
        from ddgs import DDGS
    except ImportError as exc:
        raise RuntimeError("Установите поиск: pip install ddgs") from exc

    collected: list[dict[str, str | None]] = []
    with DDGS(timeout=settings.SEARCH_TIMEOUT) as ddgs:
        for query in queries:
            try:
                collected.extend(
                    _collect_ddgs_items(ddgs, query, max_results=max_results)
                )
            except Exception:
                continue
    return collected


def web_search_multi(
    queries: list[str],
    kind: str = "general",
    cities: list[str] | None = None,
) -> dict[str, Any]:
    """
    Несколько запросов, дедупликация и фильтр по типу инструмента (tickets/events/dining).
    """
    tavily_key = os.getenv("TAVILY_API_KEY", "").strip()
    all_results: list[dict[str, str | None]] = []
    answers: list[str] = []

    if tavily_key:
        for query in queries:
            try:
                data = _search_via_tavily(query, tavily_key)
                if data.get("answer"):
                    answers.append(str(data["answer"]))
                all_results.extend(data.get("results", []))
            except Exception:
                continue
        provider = "tavily"
    else:
        per_query_limit = settings.KIND_MAX_RESULTS.get(kind, settings.MAX_SEARCH_RESULTS)
        all_results = _search_via_ddgs_batch(queries, max_results=per_query_limit)
        provider = "ddgs"

    raw_count = len(_dedupe_results(all_results))
    merged = _filter_results(_dedupe_results(all_results), kind, cities)

    used_fallback = False
    if not merged and all_results:
        merged = _dedupe_results(all_results)[:8]
        used_fallback = True

    return {
        "provider": provider,
        "kind": kind,
        "queries": queries,
        "answer": "\n".join(answers) if answers else None,
        "results": merged,
        "results_count": len(merged),
        "raw_results_count": raw_count,
        "filter_fallback": used_fallback,
    }
