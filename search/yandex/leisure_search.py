"""Поиск мест досуга через HTTP Геокодер (ключ API Геокодера)."""

from __future__ import annotations

import math

from models.routes import GeoPoint, LeisureTag, PoiPoint
from search.yandex.city_landmarks import (
    fallback_coords,
    seed_to_feature,
    seeds_for_city,
)
from search.yandex.client import (
    center_bbox,
    geocode_city,
    geocode_places,
    get_api_key,
)
from search.yandex.leisure_tags import (
    geocode_queries_for_tag,
    leisure_pool_limit,
)
from search.yandex.parse import feature_to_poi
from search.yandex.poi_filters import (
    coord_key,
    is_acceptable_place_name,
    within_walkable_radius,
)


def _rank_key(poi: PoiPoint) -> tuple[float, float]:
    rating = poi.rating if poi.rating is not None else 0.0
    return (rating, 1.0 if poi.address else 0.0)


def _append_poi(
    collected: list[PoiPoint],
    seen_ids: set[str],
    seen_coords: set[str],
    feature: dict,
    *,
    tag: LeisureTag,
    center: GeoPoint,
) -> bool:
    poi = feature_to_poi(feature, tag=tag)
    if poi is None or poi.poi_id in seen_ids:
        return False
    if not is_acceptable_place_name(poi.name):
        return False
    if not within_walkable_radius(poi.coordinates, center):
        return False
    key = coord_key(poi.coordinates)
    if key in seen_coords:
        return False
    seen_ids.add(poi.poi_id)
    seen_coords.add(key)
    collected.append(poi)
    return True


def _collect_from_seeds(
    *,
    city: str,
    categories: list[LeisureTag],
    center: GeoPoint,
    bbox: str,
    limit: int,
    collected: list[PoiPoint],
    seen_ids: set[str],
    seen_coords: set[str],
) -> None:
    for seed in seeds_for_city(city, categories):
        if len(collected) >= limit:
            break
        features: list[dict] = []
        if get_api_key():
            batch = geocode_places(
                seed.query,
                results=3,
                bbox=bbox,
                city_hint=city,
            )
            for feature in batch:
                meta = feature.get("properties", {}).get("CompanyMetaData", {})
                if is_acceptable_place_name(str(meta.get("name") or "")):
                    meta["name"] = seed.name
                    props = feature.setdefault("properties", {})
                    props["name"] = seed.name
                    features.append(feature)
                    break
        if not features:
            coords = fallback_coords(seed)
            if coords is None or not within_walkable_radius(coords, center):
                continue
            features = [seed_to_feature(seed)]
        for feature in features:
            if _append_poi(
                collected,
                seen_ids,
                seen_coords,
                feature,
                tag=seed.tag,
                center=center,
            ):
                break


def _collect_from_tags(
    *,
    city: str,
    categories: list[LeisureTag],
    center: GeoPoint,
    bbox: str,
    limit: int,
    collected: list[PoiPoint],
    seen_ids: set[str],
    seen_coords: set[str],
) -> None:
    for tag in categories:
        if len(collected) >= limit:
            break
        per_tag_limit = max(3, limit // max(len(categories), 1))
        for query in geocode_queries_for_tag(tag, city):
            if len(collected) >= limit:
                break
            batch = geocode_places(
                query,
                results=min(10, per_tag_limit),
                bbox=bbox,
                city_hint=city,
            )
            for feature in batch:
                if len(collected) >= limit:
                    break
                _append_poi(
                    collected,
                    seen_ids,
                    seen_coords,
                    feature,
                    tag=tag,
                    center=center,
                )


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
    center = GeoPoint(lon=lon, lat=lat)
    bbox = center_bbox(lon, lat)
    limit = leisure_pool_limit(pace)
    seen_ids: set[str] = set()
    seen_coords: set[str] = set()
    collected: list[PoiPoint] = []

    _collect_from_seeds(
        city=city,
        categories=categories,
        center=center,
        bbox=bbox,
        limit=limit,
        collected=collected,
        seen_ids=seen_ids,
        seen_coords=seen_coords,
    )
    if len(collected) < limit and get_api_key():
        _collect_from_tags(
            city=city,
            categories=categories,
            center=center,
            bbox=bbox,
            limit=limit,
            collected=collected,
            seen_ids=seen_ids,
            seen_coords=seen_coords,
        )
    if not collected and not get_api_key():
        collected = _demo_leisure(city, categories, lon, lat, spn_lon, spn_lat, limit)

    collected.sort(key=_rank_key, reverse=True)
    return collected[:limit]


def _demo_leisure(
    city: str,
    categories: list[LeisureTag],
    lon: float,
    lat: float,
    spn_lon: float,
    spn_lat: float,
    limit: int,
) -> list[PoiPoint]:
    """Демо-POI без ключа."""
    from search.yandex.leisure_tags import TAG_SPECS

    collected: list[PoiPoint] = []
    seen_ids: set[str] = set()
    index = 0
    for tag in categories:
        if len(collected) >= limit:
            break
        label = TAG_SPECS[tag].label_ru
        name = f"{label} {city} #{index + 1}"
        angle = (index * 2.399963) % (2 * math.pi)
        radius_lon = spn_lon * 0.12 * (0.6 + (index % 3) * 0.2)
        radius_lat = spn_lat * 0.12 * (0.6 + (index % 2) * 0.25)
        point_lon = lon + math.cos(angle) * radius_lon
        point_lat = lat + math.sin(angle) * radius_lat
        feature = {
            "geometry": {"coordinates": [point_lon, point_lat]},
            "properties": {
                "CompanyMetaData": {
                    "name": name,
                    "url": f"https://yandex.ru/maps/org/demo_{tag}/{index}",
                    "address": city,
                    "rating": {"value": 4.5 - (index % 5) * 0.1},
                }
            },
        }
        poi = feature_to_poi(feature, tag=tag)
        if poi and poi.poi_id not in seen_ids:
            seen_ids.add(poi.poi_id)
            collected.append(poi)
        index += 1
    return collected
