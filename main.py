"""
Туристический ассистент на LangGraph.

Установка зависимостей:
    pip install "langgraph>=0.2" "langchain>=0.3" langchain-openai langchain-core python-dotenv pydantic requests ddgs

Переменные окружения (.env) — см. .env.example:
    OPENAI_API_KEY=sk-...
    PROXY_BASE_URL=https://openai.api.proxyapi.ru/v1
    TAVILY_API_KEY=...   # опционально, для более точного поиска

Запуск:
    python main.py
    # программа запросит город, даты, город вылета и ваш запрос в терминале
"""

from __future__ import annotations

import json
import os
import re
from typing import Annotated, Any, Literal, TypedDict

import requests

from dotenv import load_dotenv
from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field, ValidationError

# Конфигурация из .env: секреты и URL провайдера не попадают в репозиторий.
load_dotenv()

# Контракт данных для @tool и финального ответа `llm_final` (json_schema).
# - *SearchInput: валидация аргументов инструментов до веб-поиска
# - FinalProgram: пять обязательных секций программы поездки
# - *NodeOutput: документируют выход узлов графа (без runtime-проверки)


class TicketsSearchInput(BaseModel):
    """Параметры поиска билетов туда-обратно (самолёт, поезд, автобус)."""

    origin_city: str = Field(..., description="Город отправления")
    destination_city: str = Field(..., description="Город назначения")
    dates: str = Field(..., description="Даты поездки в свободной форме")


class CultureEventsInput(BaseModel):
    """Параметры поиска культурных мероприятий и музеев."""

    city: str = Field(..., description="Город пребывания")
    dates: str = Field(..., description="Даты поездки")


class DiningTransportInput(BaseModel):
    """Параметры поиска ресторанов и городского транспорта."""

    city: str = Field(..., description="Город пребывания")
    dates: str = Field(..., description="Даты поездки")


class PlannerContext(BaseModel):
    """Контекст планировщика: город, даты и город вылета."""

    city: str
    dates: str
    origin_city: str


class FinalProgram(BaseModel):
    """Структурированная культурная программа поездки."""

    tickets: str = Field(
        ...,
        description="Билеты туда-обратно: самолёт, поезд (РЖД), автобус — со ссылками",
    )
    events: str = Field(
        ...,
        description="Музеи, выставки, мероприятия (желательно в одном районе для прогулок)",
    )
    dining: str = Field(
        ...,
        description="Рестораны и кафе со ссылками, рядом с мероприятиями (пешая доступность)",
    )
    transport: str = Field(..., description="Транспортная логистика в городе")
    lifehacks: str = Field(..., description="Полезные лайфхаки для туриста")


class PlannerNodeOutput(BaseModel):
    """Структурированный результат узла planner (для документирования контракта)."""

    message: AIMessage


class ExecutorNodeOutput(BaseModel):
    """Структурированный результат узла executor: список ответов инструментов."""

    tool_messages: list[ToolMessage]


# Политика ввода из терминала: длина и эвристики prompt-injection до HumanMessage.
# - _MAX_LENGTHS: потолки по полям (city/dates/message)
# - _INJECTION_PATTERNS: RU+EN шаблоны jailbreak и подмены роли
# - sanitize_and_validate: ValueError → отказ запуска в __main__

_MAX_LENGTHS: dict[str, int] = {
    "city": 500,
    "dates": 500,
    "message": 2000,
}

_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"ignore\s+(all\s+)?(previous|prior)\s+instructions",
        r"disregard\s+(all\s+)?(previous|prior)",
        r"system\s*:",
        r"assistant\s*:",
        r"<\|",
        r"\{\{",
        r"```",
        r"jailbreak",
        r"you\s+are\s+now",
        r"новые\s+инструкции",
        r"забудь\s+(все|предыдущ)",
        r"игнорируй\s+(все|предыдущ)",
    )
]


def sanitize_and_validate(text: str, field_name: str) -> str:
    """
    Очищает и проверяет пользовательский ввод на инъекции и чрезмерную длину.
    Возвращает нормализованную строку или выбрасывает ValueError.
    """
    cleaned = text.strip()
    if not cleaned:
        raise ValueError(f"Поле «{field_name}» не может быть пустым.")

    max_len = _MAX_LENGTHS.get(field_name, 2000)
    if len(cleaned) > max_len:
        raise ValueError(
            f"Поле «{field_name}» слишком длинное (максимум {max_len} символов)."
        )

    for pattern in _INJECTION_PATTERNS:
        if pattern.search(cleaned):
            raise ValueError(
                f"Поле «{field_name}» содержит подозрительные конструкции и отклонено."
            )

    return cleaned


# Веб-поиск живых данных: Tavily при наличии ключа, иначе ddgs (ru-ru).
# - web_search_multi: дедуп + фильтр по kind, fallback если фильтр пуст
# - _run_search_tool: digest + instruction для LLM (только факты из ссылок)
# - Ошибки поиска не роняют граф — JSON с live_data=false

_SEARCH_TIMEOUT = 30
_MAX_SEARCH_RESULTS = 10
_KIND_MAX_RESULTS: dict[str, int] = {
    "tickets": 12,
    "events": 12,
    "restaurants": 18,
    "transport": 8,
    "dining": 14,
}
# Сколько пунктов попадает в digest для LLM (чтобы не переполнить контекст)
_DIGEST_LIMITS: dict[str, int] = {
    "tickets": 25,
    "events": 15,
    "restaurants": 20,
    "transport": 10,
}
_DDG_REGION = "ru-ru"

# Постфильтрация сниппетов по категории инструмента (kind).
# - include_any / exclude_any: отсекаем кросс-категорийный мусор (музеи в tickets)
# - events/dining: доп. проверка города через _city_aliases
# - tickets: город в сниппете не проверяем — важен маршрут origin→destination
_SEARCH_FILTERS: dict[str, dict[str, tuple[str, ...]]] = {
    "tickets": {
        "include_any": (
            "авиа",
            "рейс",
            "aviasales",
            "travel.yandex",
            "путешеств",
            "самолёт",
            "самолет",
            "аэрофлот",
            "победа",
            "rzd",
            "ржд",
            "жд билет",
            "tutu.ru",
            "tutu",
            "поезд",
            "плацкарт",
            "купе",
            "автобус",
            "bus.ru",
            "avibus",
            "blablacar",
            "flixbus",
            "eurobus",
        ),
        "exclude_any": (
            "музей",
            "эрмитаж",
            "фаберже",
            "афиша",
            "ресторан",
            "выставк",
            "концерт",
            "театр",
            "tripadvisor",
            "kinopoisk",
            "кинопоиск",
        ),
    },
    "events": {
        "include_any": (
            "музей",
            "выставк",
            "афиша",
            "концерт",
            "театр",
            "kassir",
            "эрмитаж",
            "филармон",
            "галере",
            "билет в музей",
        ),
        "exclude_any": (
            "aviasales",
            "travel.yandex",
            "ресторан",
            "tripadvisor",
            "2gis.ru/restaurant",
            "kinopoisk",
        ),
    },
    "restaurants": {
        "include_any": (
            "ресторан",
            "кафе",
            "2gis",
            "tripadvisor",
            "yandex.ru/maps",
            "яндекс.карт",
            "где поесть",
            "заведен",
            "кухн",
            "меню",
        ),
        "exclude_any": (
            "aviasales",
            "rzd.ru",
            "kinopoisk",
            "кинопоиск",
            "музей",
            "афиша",
            "метро схем",
        ),
    },
    "transport": {
        "include_any": (
            "метро",
            "транспорт",
            "маршрут",
            "яндекс.карт",
            "общественный",
            "проезд",
            "карта метро",
            "2gis",
        ),
        "exclude_any": (
            "aviasales",
            "ресторан",
            "tripadvisor",
            "kinopoisk",
        ),
    },
    "dining": {
        "include_any": (
            "ресторан",
            "кафе",
            "2gis",
            "tripadvisor",
            "метро",
            "транспорт",
            "маршрут",
            "яндекс.карт",
            "общественный",
        ),
        "exclude_any": (
            "aviasales",
            "kinopoisk",
            "кинопоиск",
            "афиша концерт",
        ),
    },
}


def _tourist_area(city: str) -> str:
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
    rules = _SEARCH_FILTERS.get(kind, {})
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
        # Город в тексте — для events/restaurants; tickets и transport без этой проверки
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


def _format_search_digest(results: list[dict[str, str | None]]) -> str:
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
            "max_results": _MAX_SEARCH_RESULTS,
            "search_depth": "advanced",
            "include_answer": True,
        },
        timeout=_SEARCH_TIMEOUT,
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
    limit = max_results or _MAX_SEARCH_RESULTS
    collected: list[dict[str, str | None]] = []
    for item in ddgs_client.text(
        query,
        region=_DDG_REGION,
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
    with DDGS(timeout=_SEARCH_TIMEOUT) as ddgs:
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
        per_query_limit = _KIND_MAX_RESULTS.get(kind, _MAX_SEARCH_RESULTS)
        all_results = _search_via_ddgs_batch(queries, max_results=per_query_limit)
        provider = "ddgs"

    raw_count = len(_dedupe_results(all_results))
    merged = _filter_results(_dedupe_results(all_results), kind, cities)

    # Fallback: пустой merged после фильтра — отдаём top-8 сырых, filter_fallback=true
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


def _run_search_tool(
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
        digest_limit = _DIGEST_LIMITS.get(kind, 15)
        digest = _format_search_digest(results[:digest_limit])

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


@tool
def search_roundtrip_tickets(
    origin_city: str,
    destination_city: str,
    dates: str,
) -> str:
    """
    Поиск билетов туда-обратно: самолёт, поезд и автобус.
    Aviasales, Яндекс.Путешествия, РЖД/Tutu, автобусные сервисы.
    """
    try:
        params = TicketsSearchInput(
            origin_city=origin_city,
            destination_city=destination_city,
            dates=dates,
        )
    except ValidationError as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)

    o, d, dt = params.origin_city, params.destination_city, params.dates
    queries = [
        f"авиабилеты {o} {d} туда обратно {dt} aviasales",
        f"рейсы {o} {d} {dt} travel.yandex.ru авиа",
        f"билеты на поезд {o} {d} {dt} rzd.ru tutu.ru",
        f"жд билеты {o} {d} РЖД расписание цена {dt}",
        f"автобус {o} {d} {dt} билеты bus.ru avibus",
    ]
    return _run_search_tool(
        params.model_dump(),
        queries,
        ["Aviasales", "Яндекс.Путешествия", "РЖД", "Tutu.ru", "Bus.ru"],
        kind="tickets",
    )


@tool
def search_culture_events(city: str, dates: str) -> str:
    """
    Поиск музеев, выставок и мероприятий через Афиша / Кассир.ру.
    Запрашивает актуальную афишу из веб-поиска.
    """
    try:
        params = CultureEventsInput(city=city, dates=dates)
    except ValidationError as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)

    area = _tourist_area(params.city)
    queries = [
        f"афиша {params.city} музеи выставки {params.dates}",
        f"куда сходить {params.city} {params.dates} kassir.ru",
        f"топ музеи {params.city} режим работы билеты",
        f"достопримечательности {params.city} {area} пешая прогулка маршрут",
        f"музеи {params.city} {area} рядом друг с другом",
    ]
    payload_str = _run_search_tool(
        params.model_dump(),
        queries,
        ["Афиша", "Кассир.ру"],
        kind="events",
    )
    payload = json.loads(payload_str)
    payload["walking_area"] = area
    payload["instruction"] = (
        f"{payload.get('instruction', '')} "
        f"Мероприятия предпочтительно в районе: {area}. "
        "Укажи, какие объекты находятся в 10–15 минутах пешком друг от друга."
    )
    return json.dumps(payload, ensure_ascii=False, indent=2)


@tool
def search_dining_and_transport(city: str, dates: str) -> str:
    """
    Поиск ресторанов (много ссылок, рядом с музеями) и городского транспорта.
    2GIS, Яндекс.Карты, TripAdvisor — в пешой доступности от мероприятий.
    """
    try:
        params = DiningTransportInput(city=city, dates=dates)
    except ValidationError as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)

    area = _tourist_area(params.city)
    restaurant_queries = [
        f"лучшие рестораны {params.city} {area} TripAdvisor",
        f"рестораны {params.city} {area} 2gis рейтинг",
        f"кафе где поесть {params.city} центр yandex maps",
        f"рестораны рядом Эрмитаж Невский {params.city}" if "петербург" in params.city.lower() else f"рестораны рядом достопримечательности {params.city} {area}",
        f"топ кафе {params.city} исторический центр отзывы",
    ]
    transport_queries = [
        f"метро {params.city} карта схема проезд",
        f"общественный транспорт {params.city} как добраться",
        f"яндекс карты {params.city} маршрут метро автобус",
    ]

    cities = [params.city]
    rest_data = web_search_multi(restaurant_queries, kind="restaurants", cities=cities)
    trans_data = web_search_multi(transport_queries, kind="transport", cities=cities)

    rest_results = rest_data.get("results", [])
    trans_results = trans_data.get("results", [])

    print(
        f"  → поиск [restaurants]: {len(rest_results)} ссылок "
        f"({rest_data.get('provider')})"
    )
    print(
        f"  → поиск [transport]: {len(trans_results)} ссылок "
        f"({trans_data.get('provider')})"
    )

    payload = {
        "services": ["2GIS", "Яндекс.Карты", "TripAdvisor"],
        "params": params.model_dump(),
        "walking_area": area,
        "live_data": True,
        "restaurants_count": len(rest_results),
        "transport_count": len(trans_results),
        "restaurants_digest": _format_search_digest(
            rest_results[: _DIGEST_LIMITS["restaurants"]]
        ),
        "transport_digest": _format_search_digest(
            trans_results[: _DIGEST_LIMITS["transport"]]
        ),
        "digest": _format_search_digest(rest_results[: _DIGEST_LIMITS["restaurants"]]),
        "search": {"restaurants": rest_data, "transport": trans_data},
        "instruction": (
            f"Рестораны подбирай в районе {area} — в 5–15 минутах пешком от музеев "
            "из search_culture_events. В разделе питания дай минимум 6–8 заведений "
            "со ссылками из restaurants_digest (название + ссылка + район/улица). "
            "Транспорт — из transport_digest. Группируй «утро: музей → обед рядом»."
        ),
    }
    if not rest_results:
        payload["warning"] = "Мало ресторанов в поиске — укажите ссылки из digest вручную."
    return json.dumps(payload, ensure_ascii=False, indent=2)


# Реестр LangChain tools: три категории поиска; executor резолвит по имени через TOOL_MAP.
TOOLS = [
    search_roundtrip_tickets,
    search_culture_events,
    search_dining_and_transport,
]
TOOL_MAP: dict[str, Any] = {t.name: t for t in TOOLS}

# LLM через ProxyAPI: planner с tool_calls, finalize со structured output.
# - OPENAI_API_KEY + PROXY_BASE_URL из .env
# - llm_with_tools: три @tool, цикл planner↔executor
# - llm_final: FinalProgram via method="json_schema" — фиксированные поля ответа

llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.2,
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("PROXY_BASE_URL", "https://openai.api.proxyapi.ru/v1"),
)

llm_with_tools = llm.bind_tools(TOOLS)
# json_schema: модель обязана вернуть все поля FinalProgram без свободного текста
llm_final = llm.with_structured_output(FinalProgram, method="json_schema")

# Состояние графа: контекст поездки + накопление messages (reducer add_messages).
# - city/dates/origin_city: задаются один раз при invoke
# - messages: append-only, не перезаписываются целиком


class AgentState(TypedDict):
    """Состояние агента: город, даты, вылет и история сообщений."""

    city: str
    dates: str
    origin_city: str
    messages: Annotated[list[AnyMessage], add_messages]


# Узлы LangGraph: planner → executor|finalize, цикл до исчерпания tool_calls.


def _build_planner_system_prompt(ctx: PlannerContext) -> str:
    """Формирует системный промпт для узла planner."""
    return (
        "Ты — туристический ассистент. Составляешь культурную программу поездки.\n"
        f"Город поездки: {ctx.city}. Даты: {ctx.dates}. Город вылета: {ctx.origin_city}.\n\n"
        "Инструменты: tickets=самолёт+поезд+автобус, events=музеи (в одном районе), "
        "dining=restaurants_digest (много ссылок, рядом с музеями). "
        "Цены — только из digest, иначе «уточните на сайте» + ссылка.\n\n"
        "Обязанности:\n"
        "1. Билеты: самолёт, поезд (РЖД/Tutu), автобус (search_roundtrip_tickets).\n"
        "2. Музеи/афиша в пешой доступности (search_culture_events).\n"
        "3. Рестораны со ссылками рядом с музеями + транспорт (search_dining_and_transport).\n\n"
        "Сначала вызови ВСЕ три инструмента, если их результатов ещё нет в истории. "
        f"Для билетов: origin_city={ctx.origin_city}, destination_city={ctx.city}, dates={ctx.dates}. "
        f"Для афиши и ресторанов: city={ctx.city}, dates={ctx.dates}. "
        "Когда все три поиска выполнены — ответь кратко без вызова инструментов."
    )


def planner_node(state: AgentState) -> dict[str, list[AnyMessage]]:
    """
    Узел планировщика: LLM анализирует запрос и формирует tool_calls
    для сбора данных или финальный ответ без инструментов.
    """
    ctx = PlannerContext(
        city=state["city"],
        dates=state["dates"],
        origin_city=state["origin_city"],
    )
    system = SystemMessage(content=_build_planner_system_prompt(ctx))
    response: AIMessage = llm_with_tools.invoke([system, *state["messages"]])

    # Контракт выхода planner: AIMessage с tool_calls или финальный текст без tools
    PlannerNodeOutput(message=response)

    return {"messages": [response]}


def executor_node(state: AgentState) -> dict[str, list[ToolMessage]]:
    """
    Узел исполнителя: tool_calls → ToolMessage.
    Ошибка инструмента → текст в ToolMessage, граф продолжается (planner видит сбой).
    """
    last = state["messages"][-1]
    if not isinstance(last, AIMessage) or not last.tool_calls:
        return {"messages": []}

    tool_messages: list[ToolMessage] = []

    for call in last.tool_calls:
        name = call["name"]
        args = call.get("args") or {}
        tool_call_id = call["id"]

        try:
            if name not in TOOL_MAP:
                raise KeyError(f"Неизвестный инструмент: {name}")
            result = TOOL_MAP[name].invoke(args)
            content = result if isinstance(result, str) else str(result)
        except Exception as exc:
            content = f"Ошибка выполнения инструмента {name}: {exc}"

        tool_messages.append(
            ToolMessage(content=content, tool_call_id=tool_call_id, name=name)
        )

    ExecutorNodeOutput(tool_messages=tool_messages)
    return {"messages": tool_messages}


def finalize_node(state: AgentState) -> dict[str, list[AnyMessage]]:
    """
    Финальный узел: формирует структурированную программу поездки
    через Pydantic (FinalProgram) и выводит её в консоль.
    """
    ctx = PlannerContext(
        city=state["city"],
        dates=state["dates"],
        origin_city=state["origin_city"],
    )
    system = SystemMessage(
        content=(
            "Составь программу по ToolMessage. Строго раздели:\n"
            "- tickets: три блока со ссылками — ✈️ самолёт, 🚂 поезд (РЖД/Tutu), 🚌 автобус "
            "(из search_roundtrip_tickets).\n"
            "- events: музеи/выставки/концерты, сгруппируй по району (пешком 10–15 мин "
            "между точками), из search_culture_events + walking_area.\n"
            "- dining: минимум 6–8 ресторанов/кафе со ссылками из restaurants_digest; "
            "у каждого укажи район и «рядом с …» (музей из events).\n"
            "- transport: метро/маршруты из transport_digest.\n"
            "- lifehacks: советы по пешим маршрутам «музей → обед → музей».\n"
            "Цены — только из digest; иначе «уточните на сайте» + ссылка.\n"
            f"Город: {ctx.city}. Даты: {ctx.dates}. Вылет из: {ctx.origin_city}."
        )
    )
    human = HumanMessage(
        content="Сформируй итоговую программу: билеты, мероприятия, питание, транспорт, лайфхаки."
    )

    program: FinalProgram = llm_final.invoke([system, *state["messages"], human])

    _print_final_program(program)

    summary = (
        f"## Билеты\n{program.tickets}\n\n"
        f"## Мероприятия\n{program.events}\n\n"
        f"## Питание\n{program.dining}\n\n"
        f"## Транспорт\n{program.transport}\n\n"
        f"## Лайфхаки\n{program.lifehacks}"
    )
    final_message = AIMessage(content=summary)
    return {"messages": [final_message]}


def _print_final_program(program: FinalProgram) -> None:
    """Печатает финальную программу в консоль по разделам."""
    sections = [
        ("Билеты", program.tickets),
        ("Мероприятия", program.events),
        ("Питание", program.dining),
        ("Транспорт", program.transport),
        ("Лайфхаки", program.lifehacks),
    ]
    print("\n" + "=" * 60)
    print("КУЛЬТУРНАЯ ПРОГРАММА ПОЕЗДКИ")
    print("=" * 60)
    for title, body in sections:
        print(f"\n--- {title} ---\n")
        print(body)
    print("\n" + "=" * 60)


def route_after_planner(state: AgentState) -> Literal["executor", "finalize"]:
    """
    Условное ребро после planner: closed set через Literal.
    tool_calls → executor; иначе все три поиска завершены → finalize.
    """
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "executor"
    return "finalize"


# Сборка графа: START→planner; planner→executor|finalize; executor→planner; finalize→END.

workflow = StateGraph(AgentState)

workflow.add_node("planner", planner_node)
workflow.add_node("executor", executor_node)
workflow.add_node("finalize", finalize_node)

workflow.add_edge(START, "planner")
workflow.add_conditional_edges(
    "planner",
    route_after_planner,
    {"executor": "executor", "finalize": "finalize"},
)
workflow.add_edge("executor", "planner")
workflow.add_edge("finalize", END)

app = workflow.compile()


# CLI-точка входа: валидация ввода, initial_state, invoke(app); без ключа — SystemExit(1).

def _prompt_line(label: str, default: str = "") -> str:
    """Запрашивает строку в терминале; Enter — значение по умолчанию."""
    if default:
        raw = input(f"{label} [{default}]: ").strip()
        return raw if raw else default
    return input(f"{label}: ").strip()


if __name__ == "__main__":
    if not os.getenv("OPENAI_API_KEY"):
        print(
            "Ошибка: не задан OPENAI_API_KEY. "
            "Создайте файл .env (см. .env.example): OPENAI_API_KEY=..."
        )
        raise SystemExit(1)

    search_backend = "Tavily" if os.getenv("TAVILY_API_KEY", "").strip() else "ddgs (ru-ru)"
    print("=" * 60)
    print("Туристический ассистент — введите данные поездки")
    print(f"Поиск данных: {search_backend}")
    print("=" * 60)

    city_raw = _prompt_line("Город поездки")
    dates_raw = _prompt_line("Даты (например, 15-18 июля 2026)")
    origin_raw = _prompt_line("Город вылета", default="Москва")
    user_message_raw = _prompt_line(
        "Ваш запрос",
        default="Составь культурную программу поездки",
    )

    try:
        city = sanitize_and_validate(city_raw, "city")
        dates = sanitize_and_validate(dates_raw, "dates")
        origin_city = sanitize_and_validate(origin_raw, "city")
        user_message = sanitize_and_validate(user_message_raw, "message")
    except ValueError as exc:
        print(f"Ошибка валидации входа: {exc}")
        raise SystemExit(1) from exc

    initial_state: AgentState = {
        "city": city,
        "dates": dates,
        "origin_city": origin_city,
        "messages": [HumanMessage(content=user_message)],
    }

    print(f"\nЗапуск: {origin_city} → {city}, {dates}")
    print("Идёт веб-поиск и формирование программы (1–2 минуты)...\n")

    try:
        app.invoke(initial_state)
    except Exception as exc:
        print(f"Ошибка выполнения графа: {exc}")
        raise SystemExit(1) from exc
