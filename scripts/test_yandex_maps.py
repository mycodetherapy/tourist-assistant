#!/usr/bin/env python3
"""Проверка ключа API Геокодера Яндекс.Карт."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_VENV_PYTHON = _ROOT / ".venv" / "bin" / "python3"
_MIN_PYTHON = (3, 10)


def _ensure_python() -> None:
    """Проект требует Python 3.10+ (Pydantic, typing). Перезапуск через .venv."""
    if sys.version_info >= _MIN_PYTHON:
        return
    if _VENV_PYTHON.is_file():
        os.execv(str(_VENV_PYTHON), [str(_VENV_PYTHON), *__file__, *sys.argv[1:]])
    print(
        "Ошибка: нужен Python 3.10+, сейчас "
        f"{sys.version_info.major}.{sys.version_info.minor}.\n"
        "Создайте venv и запустите снова:\n"
        "  python3 -m venv .venv && source .venv/bin/activate\n"
        "  pip install -r requirements.txt\n"
        "  python3 scripts/test_yandex_maps.py Москва",
        file=sys.stderr,
    )
    raise SystemExit(1)


_ensure_python()

if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import config.settings  # noqa: F401 — загружает .env

from onboarding.preferences import TripPreferences
from search.yandex.client import check_api_access, geocode_city, get_api_key
from search.yandex.materials import run_route_materials_search


def main() -> int:
    key = get_api_key()
    print("YANDEX_MAPS_API_KEY (API Геокодера):", "задан" if key else "нет")
    print(f"Python: {sys.version_info.major}.{sys.version_info.minor}")

    status = check_api_access()
    print(f"Geocoder OK: {status.geocoder_ok}")
    if status.geocoder_error:
        print(f"  ошибка: {status.geocoder_error}")
    print(f"Поиск мест OK: {status.places_ok}")
    if status.places_error:
        print(f"  ошибка: {status.places_error}")

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
    for poi in materials.leisure_points[:5]:
        print(f"  - {poi.name} @ {poi.coordinates.lat:.4f},{poi.coordinates.lon:.4f}")

    if not status.geocoder_ok:
        print(
            "\nПодсказка: в https://developer.tech.yandex.ru/ подключите "
            "продукт «API Геокодера» (не JavaScript API) и вставьте ключ в YANDEX_MAPS_API_KEY."
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
