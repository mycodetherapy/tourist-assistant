"""Города для bus.tutu.ru через api-bus.tutu.ru (id + slug в path)."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

import requests

_TUTU_BUS_API = os.getenv("TUTU_BUS_API_URL", "https://api-bus.tutu.ru").rstrip("/")
_USER_AGENT = os.getenv(
    "NOMINATIM_USER_AGENT",
    "tourist-assistant/1.0 (local dev; contact: dev@localhost)",
)


def _translit_name(geopoint: dict[str, Any]) -> str | None:
    for item in geopoint.get("names") or []:
        if not isinstance(item, dict):
            continue
        if item.get("langCode") == "ru@translit":
            name = str(item.get("name") or "").strip()
            if name:
                return name
    return None


@lru_cache(maxsize=256)
def resolve_tutu_bus_city(city: str) -> tuple[str, str] | None:
    """
    (gorod_path, numeric_id) для bus.tutu.ru, например
    ('gorod_Moskva', '1447874').
    """
    cleaned = city.strip()
    if not cleaned:
        return None
    try:
        response = requests.get(
            f"{_TUTU_BUS_API}/v1/geo/suggest/",
            params={"name": cleaned},
            headers={
                "User-Agent": _USER_AGENT,
                "Accept": "application/json",
                "Referer": "https://bus.tutu.ru/",
                "Origin": "https://bus.tutu.ru",
            },
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError, TypeError):
        return None

    data = payload.get("data") if isinstance(payload, dict) else None
    geopoints = data.get("geopoints") if isinstance(data, dict) else None
    if not isinstance(geopoints, list) or not geopoints:
        return None
    geopoint = geopoints[0]
    if not isinstance(geopoint, dict):
        return None
    point_id = geopoint.get("id")
    translit = _translit_name(geopoint)
    if point_id is None or not translit:
        return None
    return f"gorod_{translit}", str(point_id)


def clear_tutu_bus_cache() -> None:
    resolve_tutu_bus_city.cache_clear()
