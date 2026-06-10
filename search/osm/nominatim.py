"""Центр города через Nominatim (бесплатно, без Yandex Geocoder)."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from functools import lru_cache

import requests

from search.city_codes import geocode_place_queries

_NOMINATIM_URL = os.getenv(
    "NOMINATIM_URL", "https://nominatim.openstreetmap.org"
).rstrip("/")
_USER_AGENT = os.getenv(
    "NOMINATIM_USER_AGENT",
    "tourist-assistant/1.0 (local dev; contact: dev@localhost)",
)
_LAST_CALL = 0.0
_MIN_INTERVAL = 1.05


@dataclass(frozen=True)
class CityCenter:
    city: str
    lon: float
    lat: float
    bbox: tuple[float, float, float, float]
    wikidata_id: str | None = None
    display_name: str = ""


def _throttle() -> None:
    global _LAST_CALL
    elapsed = time.monotonic() - _LAST_CALL
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)
    _LAST_CALL = time.monotonic()


def _parse_bbox(raw: list[str] | None) -> tuple[float, float, float, float] | None:
    if not raw or len(raw) < 4:
        return None
    try:
        south, north, west, east = (float(v) for v in raw[:4])
        return west, south, east, north
    except (TypeError, ValueError):
        return None


def _bbox_around(lon: float, lat: float, *, half_km: float = 5.0) -> tuple[float, float, float, float]:
    """Приблизительная рамка ±half_km от центра (west, south, east, north)."""
    import math

    dlat = half_km / 111.0
    dlon = half_km / (111.0 * max(0.35, abs(math.cos(math.radians(lat)))))
    return lon - dlon, lat - dlat, lon + dlon, lat + dlat


def walkable_bbox(
    center: CityCenter,
    *,
    radius_km: float | None = None,
) -> tuple[float, float, float, float]:
    half = radius_km if radius_km is not None else 4.5
    return _bbox_around(center.lon, center.lat, half_km=half)


_PLACE_ADDRESSTYPES = frozenset(
    {"city", "town", "municipality", "village", "hamlet", "suburb"}
)


def _nominatim_item_score(item: dict) -> tuple[int, float, int]:
    """Выше — лучше: place/city важнее administrative boundary (Москва → 55.75, не 55.62)."""
    category = str(item.get("category") or "")
    addresstype = str(item.get("addresstype") or "")
    typ = str(item.get("type") or "")
    try:
        importance = float(item.get("importance") or 0)
    except (TypeError, ValueError):
        importance = 0.0
    try:
        place_rank = int(item.get("place_rank") or 0)
    except (TypeError, ValueError):
        place_rank = 0

    if category == "place" and addresstype in _PLACE_ADDRESSTYPES:
        tier = 3
    elif typ == "city":
        tier = 2
    elif category == "boundary" and addresstype in {"state", "region"}:
        tier = -1
    elif category == "boundary":
        tier = 0
    else:
        tier = 1
    return tier, importance, place_rank


def _pick_best_nominatim_item(items: list[dict]) -> dict | None:
    candidates = [item for item in items if isinstance(item, dict)]
    if not candidates:
        return None
    return max(candidates, key=_nominatim_item_score)


def _search_nominatim(query: str) -> CityCenter | None:
    _throttle()
    try:
        response = requests.get(
            f"{_NOMINATIM_URL}/search",
            params={
                "q": query,
                "format": "jsonv2",
                "limit": 5,
                "addressdetails": 1,
                "extratags": 1,
            },
            headers={"User-Agent": _USER_AGENT},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return None
    if not payload:
        return None
    item = _pick_best_nominatim_item(payload)
    if item is None:
        return None
    try:
        lon = float(item["lon"])
        lat = float(item["lat"])
    except (KeyError, TypeError, ValueError):
        return None
    bbox = _parse_bbox(item.get("boundingbox")) or _bbox_around(lon, lat)
    extratags = item.get("extratags") or {}
    wikidata = str(extratags.get("wikidata") or "").strip() or None
    city_label = query.split(",")[0].strip()
    return CityCenter(
        city=city_label,
        lon=lon,
        lat=lat,
        bbox=bbox,
        wikidata_id=wikidata,
        display_name=str(item.get("display_name") or query),
    )


def _search_nominatim_many(query: str, *, limit: int = 3) -> list[dict]:
    _throttle()
    try:
        response = requests.get(
            f"{_NOMINATIM_URL}/search",
            params={
                "q": query,
                "format": "jsonv2",
                "limit": limit,
                "addressdetails": 0,
            },
            headers={"User-Agent": _USER_AGENT},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return []
    return [item for item in payload if isinstance(item, dict)]


def fetch_nominatim_embankments(
    city: str,
    center: CityCenter,
    *,
    max_items: int = 4,
) -> list["PoiPoint"]:
    """Именованные набережные города через Nominatim (дополняет Wikidata)."""
    from models.routes import GeoPoint, PoiPoint
    from search.city_codes import geocode_place_queries
    from search.yandex.poi_filters import (
        coord_key,
        is_embankment_poi_name,
        route_name_key,
        walkable_radius_km,
        within_walkable_radius,
    )

    geo = GeoPoint(lon=center.lon, lat=center.lat)
    queries: list[str] = []
    for place in geocode_place_queries(city):
        queries.extend(
            [
                f"набережная, {place}",
                f"набережная реки, {place}",
                f"речная набережная, {place}",
            ]
        )

    collected: list[PoiPoint] = []
    seen_names: set[str] = set()
    seen_coords: set[str] = set()

    for query in queries:
        if len(collected) >= max_items:
            break
        for item in _search_nominatim_many(query, limit=3):
            name = str(item.get("name") or item.get("display_name") or "").split(",")[0].strip()
            if not is_embankment_poi_name(name, city_hint=city):
                continue
            name_key = route_name_key(name)
            if name_key in seen_names:
                continue
            try:
                lon = float(item["lon"])
                lat = float(item["lat"])
            except (KeyError, TypeError, ValueError):
                continue
            coords = GeoPoint(lon=lon, lat=lat)
            if not within_walkable_radius(
                coords, geo, max_km=walkable_radius_km(city)
            ):
                continue
            ckey = coord_key(coords)
            if ckey in seen_coords:
                continue
            osm_type = str(item.get("osm_type") or "node")
            osm_id = item.get("osm_id")
            poi_id = (
                f"osm_{osm_type}_{osm_id}"
                if osm_id is not None
                else f"nominatim_emb_{ckey}"
            )
            collected.append(
                PoiPoint(
                    poi_id=poi_id,
                    tag="embankments",
                    name=name,
                    coordinates=coords,
                    maps_url=f"https://yandex.ru/maps/?pt={lon},{lat}&z=16",
                    rating=None,
                    address="",
                )
            )
            seen_names.add(name_key)
            seen_coords.add(ckey)
    return collected


@lru_cache(maxsize=256)
def resolve_city_center(city: str) -> CityCenter | None:
    """Геокодинг города через Nominatim → центр, bbox, опционально Wikidata Q-id."""
    cleaned = city.strip()
    if not cleaned:
        return None
    for query in geocode_place_queries(cleaned):
        center = _search_nominatim(query)
        if center is not None:
            return CityCenter(
                city=cleaned,
                lon=center.lon,
                lat=center.lat,
                bbox=center.bbox,
                wikidata_id=center.wikidata_id,
                display_name=center.display_name,
            )
    return None
