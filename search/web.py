"""Веб-поиск живых данных: Tavily при наличии ключа, иначе ddgs (ru-ru)."""

from __future__ import annotations

import json
import os
from typing import Any

import requests

from config import settings


def tourist_area(city: str) -> str:
    """Туристический район для подбора мероприятий и ресторанов в пешей доступности."""
    normalized = city.lower().strip()
    areas: dict[str, str] = {
        "санкт-петербург": "центр, Невский проспект, Дворцовая, Петропавловская крепость",
        "москва": "центр, Китай-город, Красная площадь, Зарядье",
        "казань": "Кремль, улица Баумана, старый город",
        "сочи": "центр Сочи, Морской вокзал, набережная",
        "екатеринбург": "исторический центр, Плотинка, Вайнера",
        "нижний новгород": "верхний город, Большая Покровская, Кремль",
    }
    for key, area in areas.items():
        if key in normalized or normalized in key:
            return area
    return "исторический центр, главные достопримечательности"


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
        if kind in {"events", "restaurants"} and city_keys:
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


def format_search_digest(results: list[dict[str, str | None]]) -> str:
    """Текстовая сводка результатов — LLM легче использует её, чем сырой JSON."""
    if not results:
        return "Результаты поиска пусты."
    lines: list[str] = []
    for index, item in enumerate(results, start=1):
        title = item.get("title") or "Без названия"
        url = item.get("url") or ""
        snippet = (item.get("snippet") or "").strip()
        block = f"{index}. {title}"
        if url:
            block += f"\n   Ссылка: {url}"
        if snippet:
            block += f"\n   Описание: {snippet}"
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


def run_search_tool(
    params: dict[str, Any],
    queries: list[str],
    services: list[str],
    kind: str,
) -> str:
    """Общая обёртка: веб-поиск + фильтр + digest для LLM."""
    cities = [
        params.get("city"),
        params.get("origin_city"),
        params.get("destination_city"),
    ]
    try:
        data = web_search_multi(queries, kind=kind, cities=cities)
        results = data.get("results", [])
        digest_limit = settings.DIGEST_LIMITS.get(kind, 15)
        digest = format_search_digest(results[:digest_limit])

        kind_hints = {
            "tickets": (
                "Билеты туда-обратно: самолёт (Aviasales), поезд (РЖД, Tutu), "
                "автобус (Bus.ru и аналоги). Дай ссылки на каждый вид транспорта."
            ),
            "events": (
                "Музеи, выставки, концерты. Группируй по району — "
                "объекты в пешей доступности друг от друга."
            ),
            "restaurants": (
                "Рестораны и кафе со ссылками (минимум 6–8 заведений). "
                "Указывай район/улицу рядом с музеями из программы."
            ),
            "transport": "Горской транспорт: метро, маршруты, карты.",
            "dining": "Рестораны, кафе и городской транспорт.",
        }

        payload = {
            "services": services,
            "params": params,
            "category": kind,
            "live_data": True,
            "results_count": len(results),
            "raw_results_count": data.get("raw_results_count", 0),
            "search_provider": data.get("provider"),
            "digest": digest,
            "search": data,
            "instruction": (
                f"{kind_hints.get(kind, '')} "
                "Используй ТОЛЬКО факты из digest (названия, цены, часы, ссылки). "
                "Не выдумывай цены — если цены нет в описании, напиши «уточните на сайте» "
                "и дай ссылку из digest."
            ),
        }
        if not results:
            payload["warning"] = (
                "После фильтрации результатов нет. Сообщи об этом и дай ссылки сервисов."
            )
        elif data.get("filter_fallback"):
            payload["warning"] = (
                "Результаты могут быть менее точными (фильтр ослаблен). "
                "Перепроверьте ссылки."
            )
        print(
            f"  → поиск [{kind}]: {len(results)} ссылок "
            f"({data.get('provider')}, всего до фильтра: {data.get('raw_results_count', 0)})"
        )
        return json.dumps(payload, ensure_ascii=False, indent=2)
    except Exception as exc:
        return json.dumps(
            {
                "live_data": False,
                "error": str(exc),
                "params": params,
                "hint": "Проверьте интернет, pip install ddgs, или задайте TAVILY_API_KEY",
            },
            ensure_ascii=False,
        )
