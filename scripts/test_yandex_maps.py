#!/usr/bin/env python3
"""Проверка сбора POI: Wikidata + discovery match."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_VENV_PYTHON = _ROOT / ".venv" / "bin" / "python3"
_MIN_PYTHON = (3, 10)


def _ensure_python() -> None:
    if sys.version_info >= _MIN_PYTHON:
        return
    if _VENV_PYTHON.is_file():
        os.execv(str(_VENV_PYTHON), [str(_VENV_PYTHON), *__file__, *sys.argv[1:]])
    print(
        "Ошибка: нужен Python 3.10+.\n"
        "  python3 -m venv .venv && source .venv/bin/activate\n"
        "  pip install -r requirements.txt\n"
        "  python3 scripts/test_yandex_maps.py Самара",
        file=sys.stderr,
    )
    raise SystemExit(1)


_ensure_python()

if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import config.settings  # noqa: F401

from onboarding.preferences import TripPreferences
from search.osm.nominatim import resolve_city_center
from search.yandex.materials import run_route_materials_search


def main() -> int:
    city = sys.argv[1] if len(sys.argv) > 1 else "Самара"
    center = resolve_city_center(city)
    print(f"Nominatim центр {city}:", center)
    if center and center.wikidata_id:
        print(f"  Wikidata: {center.wikidata_id}")

    prefs = TripPreferences(
        pace="moderate",
        budget="medium",
        transport_preference="mixed",
        travel_party="couple",
    )
    materials, warnings, discovery, poi_sources = run_route_materials_search(
        city=city,
        dates="тест",
        preferences=prefs,
    )
    print(f"Пул: {len(materials.leisure_points)} досуг")
    print(f"provider: {materials.provider}")
    if poi_sources:
        print(f"OSM: {poi_sources.get('osm_count')}, Wikidata: {poi_sources.get('wikidata_count')}")
    if discovery is not None:
        print(
            f"Discovery: {len(discovery.landmark_names)} названий "
            f"({discovery.provider}), matched={len(discovery.matched_pois)}"
        )
    for w in warnings:
        print(f"WARNING: {w}")
    for poi in materials.leisure_points[:8]:
        print(
            f"  - {poi.name} ({poi.tag}) @ "
            f"{poi.coordinates.lat:.4f},{poi.coordinates.lon:.4f} id={poi.poi_id}"
        )

    if materials.provider == "fallback":
        print("\nПодсказка: проверьте сеть и доступ к Wikidata/Nominatim.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
