"""Единый пул POI на поездку: досуг + питание."""

from __future__ import annotations

from onboarding.preferences import TripPreferences
from models.routes import RouteMaterials
from search.yandex.client import YandexApiStatus, check_api_access, get_api_key
from search.yandex.demo import has_real_leisure
from search.yandex.leisure_search import search_leisure_points
from search.yandex.leisure_tags import default_geocoder_tags


def format_materials_digest(materials: RouteMaterials) -> str:
    lines: list[str] = []
    lines.append(f"Город: {materials.city}. Даты: {materials.dates}.")
    lines.append(f"Мест досуга: {len(materials.leisure_points)}.")
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


def _materials_warnings(status: YandexApiStatus, leisure_count: int) -> list[str]:
    warnings: list[str] = []
    if not get_api_key():
        warnings.append(
            "YANDEX_MAPS_API_KEY не задан — демо-точки. "
            "Нужен ключ продукта «API Геокодера»."
        )
        return warnings
    if not status.geocoder_ok:
        warnings.append(
            "API Геокодера не принял ключ (403). В кабинете подключите "
            "продукт «API Геокодера» (не JavaScript API) и перезапустите API."
        )
    elif not status.places_ok:
        warnings.append(
            "Геокодер отвечает, но мало POI по шаблонным запросам — "
            "попробуйте другой город."
        )
    if leisure_count == 0:
        warnings.append("Пул мест пуст — маршруты соберутся из демо-точек.")
    return warnings


def run_route_materials_search(
    *,
    city: str,
    dates: str,
    preferences: TripPreferences | None = None,
) -> tuple[RouteMaterials, list[str]]:
    prefs = preferences or TripPreferences(
        pace="moderate",
        budget="medium",
        transport_preference="mixed",
        travel_party="couple",
    )
    categories = default_geocoder_tags()

    status = check_api_access()
    leisure = search_leisure_points(city=city, categories=categories, pace=prefs.pace)
    dining: list = []
    if leisure and status.geocoder_ok and has_real_leisure(leisure):
        provider = "yandex_maps"
    else:
        provider = "fallback"

    materials = RouteMaterials(
        provider=provider,
        city=city,
        dates=dates,
        leisure_points=leisure,
        dining_options=dining,
    )
    return materials, _materials_warnings(status, len(leisure))
