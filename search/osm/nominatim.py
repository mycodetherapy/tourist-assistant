"""Центр города через Nominatim (бесплатно, без Yandex Geocoder)."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

import requests

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


def walkable_bbox(center: CityCenter, *, radius_km: float = 4.5) -> tuple[float, float, float, float]:
    return _bbox_around(center.lon, center.lat, half_km=radius_km)


def resolve_city_center(city: str) -> CityCenter | None:
    """Геокодинг города через Nominatim → центр, bbox, опционально Wikidata Q-id."""
    query = f"{city.strip()}, Россия"
    _throttle()
    try:
        response = requests.get(
            f"{_NOMINATIM_URL}/search",
            params={
                "q": query,
                "format": "jsonv2",
                "limit": 1,
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
    item = payload[0]
    try:
        lon = float(item["lon"])
        lat = float(item["lat"])
    except (KeyError, TypeError, ValueError):
        return None
    bbox = _parse_bbox(item.get("boundingbox")) or _bbox_around(lon, lat)
    extratags = item.get("extratags") or {}
    wikidata = str(extratags.get("wikidata") or "").strip() or None
    return CityCenter(
        city=city.strip(),
        lon=lon,
        lat=lat,
        bbox=bbox,
        wikidata_id=wikidata,
        display_name=str(item.get("display_name") or query),
    )
