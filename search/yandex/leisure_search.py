"""Поиск мест досуга через HTTP Геокодер (ключ API Геокодера)."""

from __future__ import annotations

import math

from models.routes import GeoPoint, LeisureTag, PoiPoint
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
    is_landmark_poi_name,
    poi_name_conflict,
    route_name_key,
    within_walkable_radius,
)


def _rank_key(poi: PoiPoint) -> tuple[float, float, float]:
    rating = poi.rating if poi.rating is not None else 0.0
    landmark = 1.0 if is_landmark_poi_name(poi.name) else 0.0
    return (landmark, rating, 1.0 if poi.address else 0.0)


def _append_poi(
    collected: list[PoiPoint],
    seen_ids: set[str],
    seen_coords: set[str],
    seen_names: set[str],
    feature: dict,
    *,
    tag: LeisureTag,
    center: GeoPoint,
    city: str,
) -> bool:
    poi = feature_to_poi(feature, tag=tag)
    if poi is None or poi.poi_id in seen_ids:
        return False
    if not is_landmark_poi_name(poi.name, city_hint=city):
        return False
    name_key = route_name_key(poi.name)
    if name_key in seen_names:
        return False
    for existing in collected:
        if poi_name_conflict(
            poi.name, poi.coordinates, existing.name, existing.coordinates
        ):
            return False
    if not within_walkable_radius(poi.coordinates, center):
        return False
    key = coord_key(poi.coordinates)
    if key in seen_coords:
        return False
    seen_ids.add(poi.poi_id)
    seen_coords.add(key)
    seen_names.add(name_key)
    collected.append(poi)
    return True


def _collect_from_discovery(
    *,
    city: str,
    center: GeoPoint,
    bbox: str,
    limit: int,
    collected: list[PoiPoint],
    seen_ids: set[str],
    seen_coords: set[str],
    seen_names: set[str],
) -> None:
    """Сначала веб-поиск названий, затем Geocoder по каждому месту."""
    from search.yandex.landmark_discovery import (
        discover_landmark_names,
        geocode_query_for_name,
        infer_tag_for_name,
    )

    names = discover_landmark_names(city)
    for name in names:
        if len(collected) >= limit:
            break
        query = geocode_query_for_name(name, city)
        if not query:
            continue
        batch = geocode_places(
            query,
            results=3,
            bbox=bbox,
            city_hint=city,
        )
        tag = infer_tag_for_name(name)
        for feature in batch:
            if len(collected) >= limit:
                break
            _append_poi(
                collected,
                seen_ids,
                seen_coords,
                seen_names,
                feature,
                tag=tag,
                center=center,
                city=city,
            )


def _collect_from_geocoder(
    *,
    city: str,
    categories: list[LeisureTag],
    center: GeoPoint,
    bbox: str,
    limit: int,
    collected: list[PoiPoint],
    seen_ids: set[str],
    seen_coords: set[str],
    seen_names: set[str],
) -> None:
    """Пул POI только из ответов HTTP Геокодера по шаблонным запросам."""
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
                    seen_names,
                    feature,
                    tag=tag,
                    center=center,
                    city=city,
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
    seen_names: set[str] = set()
    collected: list[PoiPoint] = []

    if get_api_key():
        _collect_from_discovery(
            city=city,
            center=center,
            bbox=bbox,
            limit=limit,
            collected=collected,
            seen_ids=seen_ids,
            seen_coords=seen_coords,
            seen_names=seen_names,
        )
        if len(collected) < limit:
            _collect_from_geocoder(
                city=city,
                categories=categories,
                center=center,
                bbox=bbox,
                limit=limit,
                collected=collected,
                seen_ids=seen_ids,
                seen_coords=seen_coords,
                seen_names=seen_names,
            )
    else:
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
