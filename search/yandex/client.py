"""HTTP-клиент Geocoder и Search API Яндекс.Карт."""

from __future__ import annotations

import os
import time
from typing import Any

import requests

_GEOCODER_URL = "https://geocode-maps.yandex.ru/1.x/"
_SEARCH_URL = "https://search-maps.yandex.ru/v1/"
_LAST_CALL = 0.0
_MIN_INTERVAL = 0.35


def get_api_key() -> str:
    return os.getenv("YANDEX_MAPS_API_KEY", "").strip()


def _throttle() -> None:
    global _LAST_CALL
    elapsed = time.monotonic() - _LAST_CALL
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)
    _LAST_CALL = time.monotonic()


def geocode_city(city: str) -> tuple[float, float, tuple[float, float]] | None:
    """
    Центр города и spn (lon_span, lat_span).
    Возвращает (lon, lat, (spn_lon, spn_lat)) или None.
    """
    key = get_api_key()
    if not key:
        return _fallback_city_center(city)
    _throttle()
    try:
        response = requests.get(
            _GEOCODER_URL,
            params={
                "apikey": key,
                "geocode": f"{city}, Россия",
                "format": "json",
                "results": 1,
            },
            timeout=15,
        )
        response.raise_for_status()
        members = (
            response.json()
            .get("response", {})
            .get("GeoObjectCollection", {})
            .get("featureMember", [])
        )
        if not members:
            return _fallback_city_center(city)
        pos = members[0]["GeoObject"]["Point"]["pos"]
        lon, lat = (float(x) for x in pos.split())
        envelope = (
            members[0]["GeoObject"]
            .get("boundedBy", {})
            .get("Envelope", {})
            .get("lowerCorner", "")
        )
        upper = (
            members[0]["GeoObject"]
            .get("boundedBy", {})
            .get("Envelope", {})
            .get("upperCorner", "")
        )
        if envelope and upper:
            lon1, lat1 = (float(x) for x in envelope.split())
            lon2, lat2 = (float(x) for x in upper.split())
            spn_lon = max(abs(lon2 - lon1), 0.08)
            spn_lat = max(abs(lat2 - lat1), 0.06)
        else:
            spn_lon, spn_lat = 0.12, 0.08
        return lon, lat, (spn_lon, spn_lat)
    except (requests.RequestException, KeyError, TypeError, ValueError):
        return _fallback_city_center(city)


def search_organizations(
    *,
    text: str,
    lon: float,
    lat: float,
    spn_lon: float = 0.12,
    spn_lat: float = 0.08,
    results: int = 20,
) -> list[dict[str, Any]]:
    key = get_api_key()
    if not key:
        return []
    _throttle()
    try:
        response = requests.get(
            _SEARCH_URL,
            params={
                "apikey": key,
                "text": text,
                "type": "biz",
                "ll": f"{lon},{lat}",
                "spn": f"{spn_lon},{spn_lat}",
                "rspn": 1,
                "results": results,
                "lang": "ru_RU",
            },
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        features = data.get("features", [])
        return features if isinstance(features, list) else []
    except (requests.RequestException, ValueError, TypeError):
        return []


_CITY_CENTERS: dict[str, tuple[float, float, tuple[float, float]]] = {
    "самара": (50.104, 53.197, (0.12, 0.08)),
    "москва": (37.618, 55.756, (0.25, 0.18)),
    "санкт-петербург": (30.314, 59.939, (0.18, 0.12)),
    "казань": (49.106, 55.796, (0.12, 0.08)),
    "сочи": (39.723, 43.586, (0.15, 0.10)),
}


def _fallback_city_center(city: str) -> tuple[float, float, tuple[float, float]] | None:
    key = city.lower().strip().replace("ё", "е")
    for name, data in _CITY_CENTERS.items():
        if name in key or key in name:
            return data
    return (37.618, 55.756, (0.25, 0.18))
