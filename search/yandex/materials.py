"""Единый пул POI на поездку: досуг + питание."""

from __future__ import annotations

from onboarding.preferences import TripPreferences
from models.routes import RouteMaterials
from search.yandex.demo import has_real_leisure
from search.yandex.landmark_discovery import (
    LandmarkDiscoveryTrace,
    format_landmark_discovery_digest,
)
from search.yandex.leisure_search import search_leisure_points
from search.yandex.leisure_tags import default_geocoder_tags


def format_materials_digest(materials: RouteMaterials) -> str:
    lines: list[str] = []
    lines.append(f"Город: {materials.city}. Даты: {materials.dates}.")
    lines.append(f"Мест досуга (полный пул для A/B/C): {len(materials.leisure_points)}.")
    for index, poi in enumerate(materials.leisure_points, start=1):
        rating = f", рейтинг {poi.rating}" if poi.rating else ""
        lines.append(
            f"L{index}. [{poi.name}]({poi.maps_url}) "
            f"(poi_id={poi.poi_id}, tag={poi.tag}{rating}) — {poi.address or 'адрес уточните'}"
        )
    lines.append(f"Ресторанов: {len(materials.dining_options)}.")
    if materials.dining_options:
        for index, dining in enumerate(materials.dining_options, start=1):
            rating = f", рейтинг {dining.rating}" if dining.rating else ""
            lines.append(
                f"R{index}. [{dining.name}]({dining.maps_url}) "
                f"(poi_id={dining.poi_id}, anchor={dining.anchor_poi_id}{rating})"
            )
    else:
        lines.append(
            "Питание вдоль маршрута — «Искать вдоль маршрута» в Яндекс.Картах после открытия ссылки."
        )
    return "\n".join(lines)


def _materials_warnings(
    leisure_count: int,
    *,
    poi_sources: dict | None,
) -> list[str]:
    warnings: list[str] = []
    if poi_sources:
        osm_count = int(poi_sources.get("osm_count") or 0)
        wd_count = int(poi_sources.get("wikidata_count") or 0)
        if osm_count == 0 and wd_count == 0:
            warnings.append(
                "Wikidata не вернула POI — проверьте сеть, WIKIDATA_SPARQL_URL "
                "или название города."
            )
    if leisure_count == 0:
        warnings.append("Пул мест пуст — маршруты соберутся из демо-точек.")
    return warnings


def run_route_materials_search(
    *,
    city: str,
    dates: str,
    preferences: TripPreferences | None = None,
) -> tuple[RouteMaterials, list[str], LandmarkDiscoveryTrace | None, dict | None]:
    prefs = preferences or TripPreferences(
        pace="moderate",
        budget="medium",
        transport_preference="mixed",
        travel_party="couple",
    )
    categories = default_geocoder_tags()

    search_result = search_leisure_points(
        city=city, categories=categories, pace=prefs.pace
    )
    leisure = search_result.points
    discovery: LandmarkDiscoveryTrace | None = None
    if search_result.landmark_discovery:
        discovery = LandmarkDiscoveryTrace(**search_result.landmark_discovery)
    dining: list = []

    if leisure and has_real_leisure(leisure):
        provider = "osm"
    else:
        provider = "fallback"

    materials = RouteMaterials(
        provider=provider,
        city=city,
        dates=dates,
        leisure_points=leisure,
        dining_options=dining,
    )
    return (
        materials,
        _materials_warnings(len(leisure), poi_sources=search_result.poi_sources),
        discovery,
        search_result.poi_sources,
    )
