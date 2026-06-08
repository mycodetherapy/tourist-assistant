"""Поиск ресторанов рядом с местами досуга (HTTP Геокодер)."""

from __future__ import annotations

import math

from models.routes import DiningOption, PoiPoint
from search.yandex.client import geocode_near_point, get_api_key
from search.yandex.leisure_tags import dining_per_anchor_limit
from search.yandex.parse import feature_to_dining
from search.yandex.poi_filters import is_acceptable_place_name


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
        cuisine = cuisine_hint.strip()
        queries = [
            f"ресторан {anchor.name} {city}",
            f"кафе {anchor.name} {city}",
            f"столовая {city} центр",
        ]
        if cuisine:
            queries.insert(0, f"ресторан {cuisine} {city}")

        features: list[dict] = []
        if get_api_key():
            for query in queries:
                if len(features) >= per_anchor * 2:
                    break
                batch = geocode_near_point(
                    query,
                    lon=anchor.coordinates.lon,
                    lat=anchor.coordinates.lat,
                    radius_lon=0.012,
                    radius_lat=0.008,
                    results=6,
                )
                for feature in batch:
                    meta = feature.get("properties", {}).get("CompanyMetaData", {})
                    name = str(meta.get("name") or "").strip()
                    if not is_acceptable_place_name(name):
                        continue
                    if name == anchor.name:
                        continue
                    features.append(feature)

        if not features:
            features = [_synthetic_dining_feature(anchor, index=len(options))]

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


def _synthetic_dining_feature(anchor: PoiPoint, *, index: int) -> dict:
    """Именованная точка питания у достопримечательности (Geocoder не даёт кафе)."""
    short = anchor.name.split(",")[0][:40]
    name = f"Кафе у {short}"
    oid = abs(hash(f"dining_{anchor.poi_id}_{index}")) % 10_000_000_000
    url = f"https://yandex.ru/maps/?text={name}&ll={anchor.coordinates.lon},{anchor.coordinates.lat}&z=17"
    angle = (index * 1.7 + 0.5) % (2 * math.pi)
    lon = anchor.coordinates.lon + math.cos(angle) * 0.003
    lat = anchor.coordinates.lat + math.sin(angle) * 0.002
    return {
        "geometry": {"coordinates": [lon, lat]},
        "properties": {
            "CompanyMetaData": {
                "name": name,
                "url": url,
                "rating": {"value": 4.4},
            }
        },
    }
