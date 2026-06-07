"""HTTP-клиент Geocoder и Search API Яндекс.Карт."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import requests

_GEOCODER_URL = "https://geocode-maps.yandex.ru/1.x/"
_SEARCH_URL = "https://search-maps.yandex.ru/v1/"
_LAST_CALL = 0.0
_MIN_INTERVAL = 0.35


@dataclass(frozen=True)
class YandexApiStatus:
    geocoder_ok: bool
    search_ok: bool
    geocoder_error: str = ""
    search_error: str = ""


def get_api_key() -> str:
    return os.getenv("YANDEX_MAPS_API_KEY", "").strip()


def get_search_api_key() -> str:
    return os.getenv("YANDEX_SEARCH_API_KEY", "").strip() or get_api_key()


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


def check_api_access() -> YandexApiStatus:
    """Проверка ключей: Geocoder и Search API — разные продукты в кабинете Яндекса."""
    geo_key = get_api_key()
    search_key = get_search_api_key()
    if not geo_key and not search_key:
        return YandexApiStatus(False, False, "ключ не задан", "ключ не задан")

    geocoder_ok = False
    search_ok = False
    geo_err = ""
    search_err = ""

    if geo_key:
        _throttle()
        try:
            response = requests.get(
                _GEOCODER_URL,
                params={
                    "apikey": geo_key,
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

    if search_key:
        _throttle()
        try:
            response = requests.get(
                _SEARCH_URL,
                params={
                    "apikey": search_key,
                    "text": "музей Москва",
                    "type": "biz",
                    "ll": "37.618,55.756",
                    "spn": "0.2,0.15",
                    "rspn": 1,
                    "results": 1,
                    "lang": "ru_RU",
                },
                timeout=15,
            )
            if response.ok:
                features = response.json().get("features", [])
                search_ok = isinstance(features, list) and len(features) > 0
                if not search_ok:
                    search_err = "Search API ответил, но организаций нет"
            else:
                search_err = _http_error_text(response)
        except requests.RequestException as exc:
            search_err = str(exc)

    return YandexApiStatus(geocoder_ok, search_ok, geo_err, search_err)


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


def geocode_places(query: str, *, results: int = 10) -> list[dict[str, Any]]:
    """
    Поиск мест через HTTP Geocoder (fallback, если Search API недоступен).
    Подходит для ключей только с Geocoder API.
    """
    key = get_api_key()
    if not key:
        return []
    _throttle()
    try:
        response = requests.get(
            _GEOCODER_URL,
            params={
                "apikey": key,
                "geocode": query,
                "format": "json",
                "results": results,
            },
            timeout=15,
        )
        if not response.ok:
            return []
        members = (
            response.json()
            .get("response", {})
            .get("GeoObjectCollection", {})
            .get("featureMember", [])
        )
        return [_geo_member_to_feature(member) for member in members]
    except (requests.RequestException, KeyError, TypeError, ValueError):
        return []


def _geo_member_to_feature(member: dict[str, Any]) -> dict[str, Any]:
    obj = member.get("GeoObject") or {}
    pos = str(obj.get("Point", {}).get("pos", ""))
    lon, lat = (float(x) for x in pos.split()) if pos else (0.0, 0.0)
    name = str(obj.get("name") or "").strip()
    meta = obj.get("metaDataProperty", {}).get("GeocoderMetaData", {})
    address = str(meta.get("text") or obj.get("description") or "").strip()
    if not name:
        name = address.split(",")[0] if address else "Место"
    maps_url = (
        f"https://yandex.ru/maps/?text={quote(name)}&ll={lon},{lat}&z=16"
    )
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


def search_organizations(
    *,
    text: str,
    lon: float,
    lat: float,
    spn_lon: float = 0.12,
    spn_lat: float = 0.08,
    results: int = 20,
) -> list[dict[str, Any]]:
    key = get_search_api_key()
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
        if not response.ok:
            return []
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
