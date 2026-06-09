"""Слияние и ранжирование пулов POI."""

from __future__ import annotations

from models.routes import GeoPoint, PoiPoint
from search.yandex.poi_filters import (
    coord_key,
    is_landmark_poi_name,
    poi_name_conflict,
    route_name_key,
    within_walkable_radius,
)


def merge_poi_pools(
    pools: list[list[PoiPoint]],
    *,
    center: GeoPoint,
    city: str,
    max_items: int = 150,
) -> list[PoiPoint]:
    collected: list[PoiPoint] = []
    seen_ids: set[str] = set()
    seen_coords: set[str] = set()
    seen_names: set[str] = set()
    for pool in pools:
        for poi in pool:
            if len(collected) >= max_items:
                return collected
            if poi.poi_id in seen_ids:
                continue
            if not is_landmark_poi_name(poi.name, city_hint=city):
                continue
            if not within_walkable_radius(poi.coordinates, center):
                continue
            name_key = route_name_key(poi.name)
            if name_key in seen_names:
                continue
            conflict = False
            for existing in collected:
                if poi_name_conflict(
                    poi.name, poi.coordinates, existing.name, existing.coordinates
                ):
                    conflict = True
                    break
            if conflict:
                continue
            key = coord_key(poi.coordinates)
            if key in seen_coords:
                continue
            seen_ids.add(poi.poi_id)
            seen_coords.add(key)
            seen_names.add(name_key)
            collected.append(poi)
    return collected


def rank_leisure_pool(
    pool: list[PoiPoint],
    *,
    boosted_poi_ids: set[str],
    match_scores: dict[str, float],
    city: str,
    limit: int,
) -> list[PoiPoint]:
    def rank_key(poi: PoiPoint) -> tuple[float, float, float, str]:
        boost = 1.0 if poi.poi_id in boosted_poi_ids else 0.0
        match = match_scores.get(poi.poi_id, 0.0)
        landmark = 1.0 if is_landmark_poi_name(poi.name, city_hint=city) else 0.0
        return (boost + match, landmark, 1.0 if poi.address else 0.0, poi.name)

    ordered = sorted(pool, key=rank_key, reverse=True)
    return ordered[:limit]
