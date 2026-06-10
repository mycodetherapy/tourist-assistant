"""HTTP Geocoder Яндекс.Карт (ключ продукта «API Геокодера»)."""

from __future__ import annotations

import os
import time
from typing import Any
from urllib.parse import quote

import requests

_GEOCODER_URL = "https://geocode-maps.yandex.ru/1.x/"
_LAST_CALL = 0.0
_MIN_INTERVAL = 0.35

from search.yandex.poi_filters import is_acceptable_geo_member


def get_api_key() -> str:
    """Ключ API Геокодера (geocode-maps.yandex.ru)."""
    return os.getenv("YANDEX_MAPS_API_KEY", "").strip()


def _throttle() -> None:
    global _LAST_CALL
    elapsed = time.monotonic() - _LAST_CALL
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)
    _LAST_CALL = time.monotonic()


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
