"""LangChain tools для поиска материалов маршрута."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import tool
from pydantic import ValidationError

from models.schemas import RouteMaterialsInput
from search.context import get_session_preferences, set_route_materials
from search.yandex.materials import (
    format_materials_digest,
    run_route_materials_search,
)
from search.yandex.landmark_discovery import format_landmark_discovery_digest

__all__ = [
    "TOOLS",
    "TOOL_MAP",
    "search_route_materials",
    "search_culture_events",
    "search_dining",
]


@tool
def search_route_materials(city: str, dates: str) -> str:
    """
    Единый пул мест досуга для всей поездки.
    POI: city pack (OSM PBF) + Wikidata fallback + веб-discovery → fuzzy-match.
    """
    try:
        params = RouteMaterialsInput(city=city, dates=dates)
    except ValidationError as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)

    prefs = get_session_preferences()
    materials, api_warnings, landmark_discovery, poi_sources = run_route_materials_search(
        city=params.city,
        dates=params.dates,
        preferences=prefs,
    )
    digest = format_materials_digest(materials)
    payload = {
        "schema_version": 1,
        "category": "route_materials",
        "provider": materials.provider,
        "live_data": True,
        "params": params.model_dump(),
        "materials": materials.model_dump(),
        "leisure_count": len(materials.leisure_points),
        "dining_count": len(materials.dining_options),
        "materials_digest": digest,
        "digest": digest,
        "instruction": (
            "Собери 3 пеших маршрута A/B/C разной длины: компактный, средний, длинный. "
            "Используй ТОЛЬКО poi_id из materials_digest. "
            "Не выдумывай места и URL."
        ),
    }
    if poi_sources:
        payload["poi_sources"] = poi_sources
    if landmark_discovery is not None:
        payload["landmark_discovery"] = landmark_discovery.to_dict()
        payload["landmark_discovery_digest"] = format_landmark_discovery_digest(
            landmark_discovery
        )
    if api_warnings:
        payload["warnings"] = api_warnings
        payload["warning"] = api_warnings[0]
    elif not materials.leisure_points:
        payload["warning"] = "Пул мест пуст — проверьте Wikidata/Nominatim или город."
    set_route_materials(materials.model_dump())
    print(
        f"  → route materials: {len(materials.leisure_points)} досуг "
        f"({materials.provider})"
    )
    return json.dumps(payload, ensure_ascii=False, indent=2)


@tool
def search_culture_events(city: str, dates: str) -> str:
    """Устарело: делегирует search_route_materials."""
    return search_route_materials.invoke({"city": city, "dates": dates})


@tool
def search_dining(city: str, dates: str) -> str:
    """Устарело: делегирует search_route_materials."""
    return search_route_materials.invoke({"city": city, "dates": dates})


TOOLS = [
    search_route_materials,
]
TOOL_MAP: dict[str, Any] = {t.name: t for t in TOOLS}
TOOL_MAP["search_culture_events"] = search_route_materials
TOOL_MAP["search_dining"] = search_route_materials
TOOL_MAP["search_dining_and_transport"] = search_route_materials
