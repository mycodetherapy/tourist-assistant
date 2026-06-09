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
    is_leisure_route_poi,
    poi_name_conflict,
    route_name_key,
    walkable_radius_km,
    within_walkable_radius,
)

# Зеркала с глобальным покрытием; kumi → private.coffee (см. wiki OSM Overpass API).
_DEFAULT_OVERPASS_ENDPOINTS = (
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass-api.de/api/interpreter",
)
_LAST_CALL = 0.0
_MIN_INTERVAL = 1.0
_TIMEOUT = int(os.getenv("OVERPASS_TIMEOUT", "60"))
_MAX_RETRIES = 2
_BATCH_SIZE = 4
_MIN_RAW_ELEMENTS = 8
_TARGET_RAW_ELEMENTS = 60

# Короткие селекторы по приоритету: сначала «жирные» теги, затем расширение.
_LEISURE_CLAUSE_TIERS: tuple[tuple[str, ...], ...] = (
    (
        'node["name"~"набереж|embankment|promenade|waterfront",i]({box})',
        'way["name"~"набереж|embankment|promenade|waterfront",i]({box})',
        'node["tourism"="museum"]({box})',
        'node["tourism"="attraction"]({box})',
    ),
    (
        'node["historic"="church"]({box})',
        'node["amenity"="place_of_worship"]["name"]({box})',
        'way["highway"="pedestrian"]["name"~"набереж",i]({box})',
        'node["highway"="pedestrian"]["name"~"набереж",i]({box})',
    ),
    (
        'node["tourism"="gallery"]({box})',
        'node["tourism"="viewpoint"]({box})',
        'node["historic"="monument"]({box})',
        'node["historic"="monastery"]({box})',
    ),
    (
        'node["amenity"="museum"]({box})',
        'node["amenity"="theatre"]({box})',
        'node["leisure"="park"]({box})',
        'node["leisure"="garden"]({box})',
    ),
    (
        'node["tourism"="artwork"]({box})',
        'node["historic"="memorial"]({box})',
        'node["historic"="cathedral"]({box})',
        'node["amenity"="arts_centre"]({box})',
    ),
    (
        'way["tourism"="museum"]({box})',
        'way["tourism"="attraction"]({box})',
        'way["historic"="church"]({box})',
        'way["leisure"="park"]({box})',
    ),
    (
        'node["leisure"="pedestrian_area"]["name"]({box})',
        'node["highway"="pedestrian"]["name"]({box})',
        'node["place"="square"]["name"]({box})',
        'node["man_made"="monument"]({box})',
    ),
    (
        'way["historic"="monument"]({box})',
        'way["leisure"="garden"]({box})',
        'way["highway"="pedestrian"]["name"]({box})',
        'node["building"="church"]["name"]({box})',
    ),
)

_HEADERS = {
    "User-Agent": os.getenv(
        "NOMINATIM_USER_AGENT",
        "tourist-assistant/1.0 (local dev; contact: dev@localhost)",
    ),
    "Accept": "application/json",
}


def _overpass_endpoints() -> list[str]:
    """URL Overpass: OVERPASS_URL или цепочка зеркал OVERPASS_URLS / defaults."""
    custom = os.getenv("OVERPASS_URL", "").strip()
    if custom:
        return [custom.rstrip("/")]
    extra = os.getenv("OVERPASS_URLS", "").strip()
    if extra:
        return [item.strip().rstrip("/") for item in extra.split(",") if item.strip()]
    return list(_DEFAULT_OVERPASS_ENDPOINTS)


def _http_timeout() -> int:
    return max(90, _TIMEOUT + 30)


def _throttle() -> None:
    global _LAST_CALL
    elapsed = time.monotonic() - _LAST_CALL
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)
    _LAST_CALL = time.monotonic()


def _bbox_clause(bbox: tuple[float, float, float, float]) -> str:
    """Overpass bbox: south,west,north,east (см. wiki Overpass API)."""
    west, south, east, north = bbox
    return f"{south},{west},{north},{east}"


def _batched_bbox_queries(
    bbox: tuple[float, float, float, float],
    *,
    tiers: tuple[tuple[str, ...], ...] | None = None,
) -> list[str]:
    box = _bbox_clause(bbox)
    tier_specs = tiers or _LEISURE_CLAUSE_TIERS
    queries: list[str] = []
    for tier in tier_specs:
        clauses = [template.format(box=box) for template in tier]
        for index in range(0, len(clauses), _BATCH_SIZE):
            batch = clauses[index : index + _BATCH_SIZE]
            inner = ";\n  ".join(batch) + ";"
            queries.append(
                f"[out:json][timeout:{_TIMEOUT}];\n(\n  {inner}\n);\nout center tags;"
            )
    return queries


def _merge_elements(batches: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    for batch in batches:
        for element in batch:
            if not isinstance(element, dict):
                continue
            key = (str(element.get("type") or ""), int(element.get("id") or 0))
            if key in seen:
                continue
            seen.add(key)
            merged.append(element)
    return merged


def _run_overpass(query: str) -> list[dict[str, Any]]:
    http_timeout = _http_timeout()
    for url in _overpass_endpoints():
        for attempt in range(_MAX_RETRIES):
            _throttle()
            try:
                response = requests.post(
                    url,
                    data={"data": query},
                    timeout=http_timeout,
                    headers=_HEADERS,
                )
                if response.status_code in {429, 502, 503, 504}:
                    if attempt + 1 >= _MAX_RETRIES:
                        break
                    time.sleep(1.5 * (attempt + 1))
                    continue
                response.raise_for_status()
                payload = response.json()
            except requests.Timeout:
                break
            except requests.ConnectionError:
                break
            except (requests.RequestException, ValueError):
                if attempt + 1 >= _MAX_RETRIES:
                    break
                time.sleep(1.0)
                continue
            else:
                elements = payload.get("elements") or []
                return [el for el in elements if isinstance(el, dict)]
    return []


def _fetch_bbox_elements(
    bbox: tuple[float, float, float, float],
    *,
    max_raw: int,
) -> list[dict[str, Any]]:
    batches: list[list[dict[str, Any]]] = []
    total = 0
    empty_streak = 0
    for query in _batched_bbox_queries(bbox):
        if total >= max_raw:
            break
        batch = _run_overpass(query)
        if batch:
            batches.append(batch)
            total = len(_merge_elements(batches))
            empty_streak = 0
        else:
            empty_streak += 1
            if empty_streak >= 2 and total == 0:
                break
            if empty_streak >= 3:
                break
        if total >= _TARGET_RAW_ELEMENTS:
            break
    return _merge_elements(batches)[:max_raw]


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
    if not is_leisure_route_poi(poi, city_hint=city):
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
        poi.coordinates,
        GeoPoint(lon=center.lon, lat=center.lat),
        max_km=walkable_radius_km(city),
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
    """POI из OSM: лёгкие bbox-запросы; при нехватке — bbox города из Nominatim."""
    radius = walkable_radius_km(city)
    walk_bbox = walkable_bbox(center, radius_km=radius)
    max_raw = max(max_elements * 2, 80)

    elements = _fetch_bbox_elements(walk_bbox, max_raw=max_raw)
    if len(elements) < _MIN_RAW_ELEMENTS and center.bbox:
        city_elements = _fetch_bbox_elements(center.bbox, max_raw=max_raw)
        if len(city_elements) > len(elements):
            elements = city_elements

    collected: list[PoiPoint] = []
    seen_ids: set[str] = set()
    seen_coords: set[str] = set()
    seen_names: set[str] = set()
    for element in elements:
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
