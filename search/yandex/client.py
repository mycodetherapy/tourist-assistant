"""HTTP Geocoder Яндекс.Карт (ключ продукта «API Геокодера»)."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import requests

_GEOCODER_URL = "https://geocode-maps.yandex.ru/1.x/"
_LAST_CALL = 0.0
_MIN_INTERVAL = 0.35

from search.yandex.poi_filters import is_acceptable_geo_member


@dataclass(frozen=True)
class YandexApiStatus:
    """Статус ключа API Геокодера."""

    geocoder_ok: bool
    places_ok: bool
    geocoder_error: str = ""
    places_error: str = ""


def get_api_key() -> str:
    """Ключ API Геокодера (geocode-maps.yandex.ru)."""
    return os.getenv("YANDEX_MAPS_API_KEY", "").strip()


def _throttle() -> None:
    global _LAST_CALL
    elapsed = time.monotonic() - _LAST_CALL
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)
    _LAST_CALL = time.monotonic()


def _http_error_text(response: requests.Response) -> str:
    text = (response.text or "").strip()
    if len(text) > 200:
        return f"HTTP {response.status_code}: {text[:200]}…"
    return f"HTTP {response.status_code}: {text}"


def city_bbox(
    lon: float,
    lat: float,
    spn_lon: float,
    spn_lat: float,
    *,
    max_half_lon: float = 0.22,
    max_half_lat: float = 0.16,
) -> str:
    """Ограничение поиска рамкой города: lon,lat~lon,lat."""
    half_lon = min(spn_lon / 2, max_half_lon)
    half_lat = min(spn_lat / 2, max_half_lat)
    return (
        f"{lon - half_lon},{lat - half_lat}~{lon + half_lon},{lat + half_lat}"
    )


def center_bbox(
    lon: float,
    lat: float,
    *,
    half_lon: float = 0.05,
    half_lat: float = 0.035,
) -> str:
    """Узкая рамка исторического центра для пеших маршрутов."""
    return f"{lon - half_lon},{lat - half_lat}~{lon + half_lon},{lat + half_lat}"


def check_api_access() -> YandexApiStatus:
    """Проверяет ключ API Геокодера."""
    key = get_api_key()
    if not key:
        return YandexApiStatus(False, False, "ключ не задан", "ключ не задан")

    geocoder_ok = False
    places_ok = False
    geo_err = ""
    places_err = ""

    _throttle()
    try:
        response = requests.get(
            _GEOCODER_URL,
            params={
                "apikey": key,
                "geocode": "Москва, Россия",
                "format": "json",
                "results": 1,
            },
            timeout=15,
        )
        if response.ok:
            members = (
                response.json()
                .get("response", {})
                .get("GeoObjectCollection", {})
                .get("featureMember", [])
            )
            geocoder_ok = bool(members)
            if not geocoder_ok:
                geo_err = "пустой ответ Geocoder"
        else:
            geo_err = _http_error_text(response)
    except requests.RequestException as exc:
        geo_err = str(exc)

    _throttle()
    try:
        places = geocode_places("музей Москва, Россия", results=3)
        places_ok = len(places) > 0
        if not places_ok:
            places_err = "Geocoder не вернул места по запросу «музей Москва»"
    except Exception as exc:
        places_err = str(exc)

    return YandexApiStatus(geocoder_ok, places_ok, geo_err, places_err)


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
        if not response.ok:
            return _fallback_city_center(city)
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


def _is_place_member(member: dict[str, Any], *, city_hint: str = "") -> bool:
    return is_acceptable_geo_member(member, city_hint=city_hint)


def geocode_places(
    query: str,
    *,
    results: int = 10,
    bbox: str | None = None,
    city_hint: str = "",
) -> list[dict[str, Any]]:
    """
    Поиск мест через HTTP Geocoder (ключ API Геокодера).
    Платный Search API и JavaScript API не используются.
    """
    key = get_api_key()
    if not key:
        return []
    _throttle()
    try:
        params: dict[str, Any] = {
            "apikey": key,
            "geocode": query,
            "format": "json",
            "results": results,
        }
        if bbox:
            params["bbox"] = bbox
            params["rspn"] = 1
        response = requests.get(_GEOCODER_URL, params=params, timeout=15)
        if not response.ok:
            return []
        members = (
            response.json()
            .get("response", {})
            .get("GeoObjectCollection", {})
            .get("featureMember", [])
        )
        out: list[dict[str, Any]] = []
        for member in members:
            if not _is_place_member(member, city_hint=city_hint):
                continue
            out.append(_geo_member_to_feature(member))
        return out
    except (requests.RequestException, KeyError, TypeError, ValueError):
        return []


def geocode_near_point(
    query: str,
    *,
    lon: float,
    lat: float,
    radius_lon: float = 0.015,
    radius_lat: float = 0.010,
    results: int = 8,
) -> list[dict[str, Any]]:
    """Поиск рядом с точкой (рестораны у достопримечательности)."""
    bbox = (
        f"{lon - radius_lon},{lat - radius_lat}~{lon + radius_lon},{lat + radius_lat}"
    )
    return geocode_places(query, results=results, bbox=bbox)


def _geo_member_to_feature(member: dict[str, Any]) -> dict[str, Any]:
    obj = member.get("GeoObject") or {}
    pos = str(obj.get("Point", {}).get("pos", ""))
    lon, lat = (float(x) for x in pos.split()) if pos else (0.0, 0.0)
    name = str(obj.get("name") or "").strip()
    meta = obj.get("metaDataProperty", {}).get("GeocoderMetaData", {})
    address = str(meta.get("text") or obj.get("description") or "").strip()
    if not name:
        name = address.split(",")[0] if address else "Место"
    maps_url = f"https://yandex.ru/maps/?text={quote(name)}&ll={lon},{lat}&z=16"
    return {
        "geometry": {"coordinates": [lon, lat]},
        "properties": {
            "name": name,
            "description": address,
            "CompanyMetaData": {
                "name": name,
                "address": address,
                "url": maps_url,
            },
        },
    }


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
