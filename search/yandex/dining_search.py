"""Поиск ресторанов рядом с местами досуга."""

from __future__ import annotations

import math

from models.routes import DiningOption, PoiPoint
from search.yandex.client import geocode_places, get_api_key, search_organizations
from search.yandex.leisure_tags import dining_per_anchor_limit
from search.yandex.parse import feature_to_dining


def search_dining_near_leisure(
    *,
    city: str,
    leisure_points: list[PoiPoint],
    min_rating: float = 4.0,
    pace: str = "moderate",
    cuisine_hint: str = "",
) -> list[DiningOption]:
    per_anchor = dining_per_anchor_limit(pace)
    options: list[DiningOption] = []
    seen: set[str] = set()

    for anchor in leisure_points:
        count = 0
        query = "ресторан кафе"
        if cuisine_hint.strip():
            query = f"{query} {cuisine_hint.strip()}"
        search_text = f"{query} {city}"
        features: list[dict] = []
        if get_api_key():
            features = search_organizations(
                text=search_text,
                lon=anchor.coordinates.lon,
                lat=anchor.coordinates.lat,
                spn_lon=0.012,
                spn_lat=0.008,
                results=10,
            )
            if not features:
                features = geocode_places(
                    f"{query} рядом с {anchor.name} {city}",
                    results=5,
                )
        if not features:
            features = _fallback_dining(anchor, index=len(options))
        for feature in features:
            dining = feature_to_dining(feature, anchor_poi_id=anchor.poi_id)
            if dining is None or dining.poi_id in seen:
                continue
            if dining.rating is not None and dining.rating < min_rating:
                continue
            seen.add(dining.poi_id)
            options.append(dining)
            count += 1
            if count >= per_anchor:
                break
    return options


def _fallback_dining(anchor: PoiPoint, *, index: int) -> list[dict]:
    oid = abs(hash(f"dining_{anchor.poi_id}_{index}")) % 10_000_000_000
    name = f"Кафе рядом с {anchor.name[:30]}"
    url = f"https://yandex.ru/maps/org/demo_cafe/{oid}"
    angle = (index * 1.7 + 0.5) % (2 * math.pi)
    lon = anchor.coordinates.lon + math.cos(angle) * 0.006
    lat = anchor.coordinates.lat + math.sin(angle) * 0.004
    return [
        {
            "geometry": {"coordinates": [lon, lat]},
            "properties": {
                "CompanyMetaData": {
                    "name": name,
                    "url": url,
                    "rating": {"value": 4.4},
                }
            },
        }
    ]
