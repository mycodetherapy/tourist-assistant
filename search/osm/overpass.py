"""Запрос leisure POI через Overpass API."""

from __future__ import annotations

import os
import time
from typing import Any

import requests

from models.routes import GeoPoint, PoiPoint
from search.osm.nominatim import CityCenter, walkable_bbox
from search.osm.poi_from_tags import osm_element_to_poi
from search.yandex.poi_filters import (
    coord_key,
    is_landmark_poi_name,
    poi_name_conflict,
    route_name_key,
    within_walkable_radius,
)

_OVERPASS_URL = os.getenv(
    "OVERPASS_URL", "https://overpass-api.de/api/interpreter"
).rstrip("/")
_LAST_CALL = 0.0
_MIN_INTERVAL = 2.0
_TIMEOUT = int(os.getenv("OVERPASS_TIMEOUT", "20"))
_MAX_RETRIES = 2
_AREA_FALLBACK_MAX_SEC = float(os.getenv("OVERPASS_AREA_FALLBACK_MAX_SEC", "12"))

_TOURISM_RE = (
    "attraction|museum|gallery|viewpoint|theme_park|artwork|zoo|aquarium"
)
_AMENITY_RE = "museum|theatre|arts_centre|planetarium"
_LEISURE_RE = "park|garden|nature_reserve"
_HISTORIC_RE = "monument|memorial|statue|castle|palace|ruins|wayside_shrine|city_gate"

_HEADERS = {
    "User-Agent": "tourist-assistant/1.0",
    "Accept": "*/*",
}


def _throttle() -> None:
    global _LAST_CALL
    elapsed = time.monotonic() - _LAST_CALL
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)
    _LAST_CALL = time.monotonic()


def _bbox_clause(bbox: tuple[float, float, float, float]) -> str:
    west, south, east, north = bbox
    return f"{south},{west},{north},{east}"


def _area_query(city: str) -> str:
    escaped = city.replace('"', '\\"')
    return f"""
[out:json][timeout:{_TIMEOUT}];
{{{{geocodeArea:"{escaped}, Россия"}}}}->.searchArea;
(
  node["tourism"~"{_TOURISM_RE}"](area.searchArea);
  way["tourism"~"{_TOURISM_RE}"](area.searchArea);
  node["historic"~"{_HISTORIC_RE}"](area.searchArea);
  way["historic"~"{_HISTORIC_RE}"](area.searchArea);
  node["amenity"~"{_AMENITY_RE}"](area.searchArea);
  way["amenity"~"{_AMENITY_RE}"](area.searchArea);
  node["leisure"~"{_LEISURE_RE}"](area.searchArea);
  way["leisure"~"{_LEISURE_RE}"](area.searchArea);
  node["man_made"="monument"](area.searchArea);
  way["man_made"="monument"](area.searchArea);
);
out center tags;
""".strip()


def _bbox_query(bbox: tuple[float, float, float, float]) -> str:
    box = _bbox_clause(bbox)
    return f"""
[out:json][timeout:{_TIMEOUT}];
(
  node["tourism"~"{_TOURISM_RE}"]({box});
  way["tourism"~"{_TOURISM_RE}"]({box});
  node["historic"~"{_HISTORIC_RE}"]({box});
  way["historic"~"{_HISTORIC_RE}"]({box});
  node["amenity"~"{_AMENITY_RE}"]({box});
  way["amenity"~"{_AMENITY_RE}"]({box});
  node["leisure"~"{_LEISURE_RE}"]({box});
  way["leisure"~"{_LEISURE_RE}"]({box});
  node["man_made"="monument"]({box});
  way["man_made"="monument"]({box});
);
out center tags;
""".strip()


def _run_overpass(query: str) -> list[dict[str, Any]]:
    for attempt in range(_MAX_RETRIES):
        _throttle()
        try:
            response = requests.post(
                _OVERPASS_URL,
                data={"data": query},
                timeout=_TIMEOUT + 15,
                headers=_HEADERS,
            )
            if response.status_code in {429, 502, 503, 504}:
                time.sleep(2.0 * (attempt + 1))
                continue
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError):
            time.sleep(1.5 * (attempt + 1))
            continue
        elements = payload.get("elements") or []
        return [el for el in elements if isinstance(el, dict)]
    return []


def _append_poi(
    collected: list[PoiPoint],
    seen_ids: set[str],
    seen_coords: set[str],
    seen_names: set[str],
    poi: PoiPoint,
    *,
    center: CityCenter,
    city: str,
) -> bool:
    if poi.poi_id in seen_ids:
        return False
    if not is_landmark_poi_name(poi.name, city_hint=city):
        return False
    name_key = route_name_key(poi.name)
    if name_key in seen_names:
        return False
    for existing in collected:
        if poi_name_conflict(
            poi.name, poi.coordinates, existing.name, existing.coordinates
        ):
            return False
    if not within_walkable_radius(
        poi.coordinates, GeoPoint(lon=center.lon, lat=center.lat)
    ):
        return False
    key = coord_key(poi.coordinates)
    if key in seen_coords:
        return False
    seen_ids.add(poi.poi_id)
    seen_coords.add(key)
    seen_names.add(name_key)
    collected.append(poi)
    return True


def fetch_overpass_leisure(
    city: str,
    center: CityCenter,
    *,
    max_elements: int = 120,
) -> list[PoiPoint]:
    """POI из OSM: bbox вокруг центра; area-запрос только если bbox быстрый и мало точек."""
    walk_bbox = walkable_bbox(center)
    bbox_started = time.monotonic()
    elements = _run_overpass(_bbox_query(walk_bbox))
    bbox_elapsed = time.monotonic() - bbox_started
    if len(elements) < 8 and bbox_elapsed <= _AREA_FALLBACK_MAX_SEC:
        elements = _run_overpass(_area_query(city)) or elements

    collected: list[PoiPoint] = []
    seen_ids: set[str] = set()
    seen_coords: set[str] = set()
    seen_names: set[str] = set()
    for element in elements[: max_elements * 2]:
        if len(collected) >= max_elements:
            break
        poi = osm_element_to_poi(element, city_hint=city)
        if poi is None:
            continue
        _append_poi(
            collected,
            seen_ids,
            seen_coords,
            seen_names,
            poi,
            center=center,
            city=city,
        )
    return collected
