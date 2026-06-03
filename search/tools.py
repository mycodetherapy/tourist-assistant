"""LangChain tools для веб-поиска по категориям поездки."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import tool
from pydantic import ValidationError

from config import settings
from models.schemas import CultureEventsInput, DiningTransportInput
from search.tickets_search import run_tickets_search
from onboarding.preferences import (
    budget_query_suffix,
    interests_query_suffix,
    restaurant_rating_suffix,
)
from search.context import enrich_query, get_session_preferences
from search.web import (
    format_search_digest,
    run_search_tool,
    tourist_area,
    web_search_multi,
)

__all__ = [
    "TOOLS",
    "TOOL_MAP",
    "search_culture_events",
    "search_dining_and_transport",
    "search_roundtrip_tickets",
]


@tool
def search_roundtrip_tickets(
    origin_city: str,
    destination_city: str,
    dates: str,
) -> str:
    """
    Билеты туда-обратно: deep links на агрегаторы с датами и маршрутом.
    Самолёт (Aviasales + API), поезд (РЖД, Tutu), автобус (Bus.tutu.ru).
    Возвращает JSON schema_version=1 с полем offers.
    """
    result = run_tickets_search(origin_city, destination_city, dates)
    return result.model_dump_json(ensure_ascii=False, indent=2)


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

    area = tourist_area(params.city)
    prefs = get_session_preferences()
    interest_hint = interests_query_suffix(prefs.interests) if prefs else ""
    queries = [
        enrich_query(
            f"афиша {params.city} музеи выставки {params.dates} {interest_hint}".strip()
        ),
        enrich_query(f"куда сходить {params.city} {params.dates} kassir.ru {interest_hint}".strip()),
        enrich_query(f"топ музеи {params.city} режим работы билеты"),
        enrich_query(f"достопримечательности {params.city} {area} пешая прогулка маршрут"),
        enrich_query(f"музеи {params.city} {area} рядом друг с другом"),
    ]
    payload_str = run_search_tool(
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

    area = tourist_area(params.city)
    prefs = get_session_preferences()
    rating_hint = (
        restaurant_rating_suffix(prefs.min_restaurant_rating) if prefs else "лучшие отзывы"
    )
    cuisine_hint = prefs.cuisine if prefs and prefs.cuisine else ""
    restaurant_queries = [
        enrich_query(
            f"лучшие рестораны {params.city} {area} TripAdvisor {rating_hint} {cuisine_hint}".strip()
        ),
        enrich_query(f"рестораны {params.city} {area} 2gis рейтинг {rating_hint}".strip()),
        enrich_query(f"кафе где поесть {params.city} центр yandex maps {cuisine_hint}".strip()),
        enrich_query(
            f"рестораны рядом Эрмитаж Невский {params.city} {rating_hint}"
            if "петербург" in params.city.lower()
            else f"рестораны рядом достопримечательности {params.city} {area} {rating_hint}"
        ),
        enrich_query(f"топ кафе {params.city} исторический центр отзывы {rating_hint}".strip()),
    ]
    transport_mode = ""
    if prefs:
        if prefs.transport_preference == "metro":
            transport_mode = "метро"
        elif prefs.transport_preference == "walking":
            transport_mode = "пешком"
        elif prefs.transport_preference == "taxi":
            transport_mode = "такси"
    transport_queries = [
        enrich_query(f"метро {params.city} карта схема проезд {transport_mode}".strip()),
        enrich_query(f"общественный транспорт {params.city} как добраться {transport_mode}".strip()),
        enrich_query(f"яндекс карты {params.city} маршрут метро автобус"),
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
        "restaurants_digest": format_search_digest(
            rest_results[: settings.DIGEST_LIMITS["restaurants"]]
        ),
        "transport_digest": format_search_digest(
            trans_results[: settings.DIGEST_LIMITS["transport"]]
        ),
        "digest": format_search_digest(rest_results[: settings.DIGEST_LIMITS["restaurants"]]),
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


TOOLS = [
    search_roundtrip_tickets,
    search_culture_events,
    search_dining_and_transport,
]
TOOL_MAP: dict[str, Any] = {t.name: t for t in TOOLS}
