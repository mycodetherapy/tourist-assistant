#!/usr/bin/env python3
"""Проверка ключей Яндекс.Карт: Geocoder и Search API."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import config.settings  # noqa: F401 — загружает .env

from search.yandex.client import check_api_access, geocode_city, get_api_key, get_search_api_key
from search.yandex.materials import run_route_materials_search
from onboarding.preferences import TripPreferences


def main() -> int:
    geo_key = get_api_key()
    search_key = get_search_api_key()
    print("YANDEX_MAPS_API_KEY:", "задан" if geo_key else "нет")
    print("YANDEX_SEARCH_API_KEY:", "задан" if search_key else "как YANDEX_MAPS_API_KEY")

    status = check_api_access()
    print(f"Geocoder OK: {status.geocoder_ok}")
    if status.geocoder_error:
        print(f"  ошибка: {status.geocoder_error}")
    print(f"Search API OK: {status.search_ok}")
    if status.search_error:
        print(f"  ошибка: {status.search_error}")

    city = sys.argv[1] if len(sys.argv) > 1 else "Москва"
    geo = geocode_city(city)
    print(f"Центр {city}:", geo)

    prefs = TripPreferences(
        pace="moderate",
        budget="medium",
        transport_preference="mixed",
        travel_party="couple",
        leisure_categories=["landmarks", "museums"],
    )
    materials, warnings = run_route_materials_search(
        city=city,
        dates="тест",
        preferences=prefs,
    )
    print(f"Пул: {len(materials.leisure_points)} досуг, {len(materials.dining_options)} ресторанов")
    print(f"provider: {materials.provider}")
    for w in warnings:
        print(f"WARNING: {w}")
    for poi in materials.leisure_points[:3]:
        print(f"  - {poi.name} @ {poi.coordinates.lat:.4f},{poi.coordinates.lon:.4f}")

    if not status.search_ok:
        print(
            "\nПодсказка: в кабинете developer.tech.yandex.ru подключите "
            "«API Поиска по организациям» и задайте YANDEX_SEARCH_API_KEY "
            "(или общий ключ с доступом к Search API)."
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
