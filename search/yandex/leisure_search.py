"""Поиск мест досуга по фиксированным тегам."""

from __future__ import annotations

import math

from models.routes import LeisureTag, PoiPoint
from search.yandex.client import (
    geocode_city,
    geocode_places,
    get_api_key,
    search_organizations,
)
from search.yandex.leisure_tags import leisure_pool_limit, search_text_for_tag
from search.yandex.parse import feature_to_poi


def _rank_key(poi: PoiPoint) -> tuple[float, float]:
    rating = poi.rating if poi.rating is not None else 0.0
    return (rating, 1.0 if poi.address else 0.0)


def _collect_features(
    *,
    city: str,
    tag: LeisureTag,
    lon: float,
    lat: float,
    spn_lon: float,
    spn_lat: float,
    limit: int,
    index: int,
) -> list[dict]:
    text = search_text_for_tag(tag, city)
    features: list[dict] = []
    if get_api_key():
        features = search_organizations(
            text=text,
            lon=lon,
            lat=lat,
            spn_lon=spn_lon,
            spn_lat=spn_lat,
            results=min(15, limit),
        )
        if not features:
            features = geocode_places(text, results=min(10, limit))
    if not features:
        features = _fallback_features(
            city,
            tag,
            lon,
            lat,
            spn_lon=spn_lon,
            spn_lat=spn_lat,
            index=index,
        )
    return features


def search_leisure_points(
    *,
    city: str,
    categories: list[LeisureTag],
    pace: str = "moderate",
) -> list[PoiPoint]:
    geo = geocode_city(city)
    if geo is None:
        return []
    lon, lat, (spn_lon, spn_lat) = geo
    limit = leisure_pool_limit(pace)
    seen_ids: set[str] = set()
    collected: list[PoiPoint] = []

    for tag in categories:
        if len(collected) >= limit:
            break
        features = _collect_features(
            city=city,
            tag=tag,
            lon=lon,
            lat=lat,
            spn_lon=spn_lon,
            spn_lat=spn_lat,
            limit=limit,
            index=len(collected),
        )
        for feature in features:
            poi = feature_to_poi(feature, tag=tag)
            if poi is None or poi.poi_id in seen_ids:
                continue
            seen_ids.add(poi.poi_id)
            collected.append(poi)
            if len(collected) >= limit:
                break

    collected.sort(key=_rank_key, reverse=True)
    return collected[:limit]


def _fallback_features(
    city: str,
    tag: LeisureTag,
    lon: float,
    lat: float,
    *,
    spn_lon: float,
    spn_lat: float,
    index: int,
) -> list[dict]:
    """Демо-POI: раскладываем по городу, а не в одну точку центра."""
    from search.yandex.leisure_tags import TAG_SPECS

    label = TAG_SPECS[tag].label_ru
    name = f"{label} {city} #{index + 1}"
    oid = abs(hash(f"{city}_{tag}_{index}")) % 10_000_000_000
    url = f"https://yandex.ru/maps/org/demo_{tag}/{oid}"
    angle = (index * 2.399963) % (2 * math.pi)
    radius_lon = spn_lon * 0.35 * (0.6 + (index % 3) * 0.2)
    radius_lat = spn_lat * 0.35 * (0.6 + (index % 2) * 0.25)
    point_lon = lon + math.cos(angle) * radius_lon
    point_lat = lat + math.sin(angle) * radius_lat
    return [
        {
            "geometry": {"coordinates": [point_lon, point_lat]},
            "properties": {
                "CompanyMetaData": {
                    "name": name,
                    "url": url,
                    "address": city,
                    "rating": {"value": 4.5 - (index % 5) * 0.1},
                }
            },
        }
    ]
