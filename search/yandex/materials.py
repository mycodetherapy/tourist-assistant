"""Единый пул POI на поездку: досуг + питание."""

from __future__ import annotations

from onboarding.preferences import TripPreferences
from models.routes import RouteMaterials
from search.yandex.client import check_api_access, get_api_key
from search.yandex.dining_search import search_dining_near_leisure
from search.yandex.leisure_search import search_leisure_points
from search.yandex.leisure_tags import normalize_leisure_categories


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
    for index, dining in enumerate(materials.dining_options, start=1):
        rating = f", рейтинг {dining.rating}" if dining.rating else ""
        lines.append(
            f"R{index}. [{dining.name}]({dining.maps_url}) "
            f"(poi_id={dining.poi_id}, anchor={dining.anchor_poi_id}{rating})"
        )
    return "\n".join(lines)


def _materials_warnings(status: object, leisure_count: int) -> list[str]:
    warnings: list[str] = []
    if not get_api_key():
        warnings.append(
            "YANDEX_MAPS_API_KEY не задан — используются демо-точки для проверки UI."
        )
        return warnings
    if not status.geocoder_ok and not status.search_ok:
        warnings.append(
            "Ключ Яндекс.Карт не принят API (403). Проверьте ключ в "
            "https://developer.tech.yandex.ru/ и перезапустите API."
        )
    elif not status.search_ok:
        warnings.append(
            "Search API (поиск организаций) недоступен для этого ключа. "
            "Нужен продукт «Поиск по организациям» или отдельный YANDEX_SEARCH_API_KEY. "
            "Пока используется Geocoder / демо-точки."
        )
    if leisure_count == 0:
        warnings.append("Пул мест пуст — маршруты будут собраны из заглушек в центре города.")
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
    categories = normalize_leisure_categories(
        prefs.leisure_categories if hasattr(prefs, "leisure_categories") else None
    )
    if not getattr(prefs, "leisure_categories", None) and prefs.interests:
        extra = []
        blob = " ".join(prefs.interests).lower()
        if "муз" in blob:
            extra.append("museums")
        if "парк" in blob:
            extra.append("parks")
        if "театр" in blob:
            extra.append("theaters")
        categories = normalize_leisure_categories(["landmarks", *extra])

    status = check_api_access()
    leisure = search_leisure_points(city=city, categories=categories, pace=prefs.pace)
    dining = search_dining_near_leisure(
        city=city,
        leisure_points=leisure,
        min_rating=prefs.min_restaurant_rating,
        pace=prefs.pace,
        cuisine_hint=prefs.cuisine,
    )
    if leisure and (status.search_ok or status.geocoder_ok):
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
