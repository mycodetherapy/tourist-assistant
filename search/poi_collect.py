"""Слияние и ранжирование пулов POI."""

from __future__ import annotations

from models.routes import GeoPoint, PoiPoint
from search.osm.poi_from_tags import _LOW_PRIORITY_WD_NAME_RE
from search.yandex.poi_filters import (
    coord_key,
    is_acceptable_place_name,
    is_embankment_poi_name,
    is_leisure_route_poi,
    poi_name_conflict,
    route_name_key,
    walkable_radius_km,
    within_walkable_radius,
)


def _is_wikidata_poi_id(poi_id: str) -> bool:
    return poi_id.startswith("Q") and poi_id[1:].isdigit()


def _pool_accepts_poi(poi: PoiPoint, *, city: str) -> bool:
    """Wikidata soft-tier уже отранжирован в fetch_wikidata_leisure."""
    if _is_wikidata_poi_id(poi.poi_id):
        if _LOW_PRIORITY_WD_NAME_RE.search(poi.name):
            return False
        if poi.tag == "embankments":
            return is_embankment_poi_name(poi.name, city_hint=city)
        return is_acceptable_place_name(poi.name, city_hint=city)
    return is_leisure_route_poi(poi, city_hint=city)


def _try_merge_poi(
    collected: list[PoiPoint],
    seen_ids: set[str],
    seen_coords: set[str],
    seen_names: set[str],
    poi: PoiPoint,
    *,
    center: GeoPoint,
    city: str,
    relax_wikidata_conflict: bool,
) -> bool:
    if poi.poi_id in seen_ids:
        return False
    if not _pool_accepts_poi(poi, city=city):
        return False
    if not within_walkable_radius(
        poi.coordinates,
        center,
        max_km=walkable_radius_km(city),
    ):
        return False
    name_key = route_name_key(poi.name)
    if name_key in seen_names:
        return False
    for existing in collected:
        relaxed = relax_wikidata_conflict and (
            _is_wikidata_poi_id(poi.poi_id) and _is_wikidata_poi_id(existing.poi_id)
        )
        if poi_name_conflict(
            poi.name,
            poi.coordinates,
            existing.name,
            existing.coordinates,
            relaxed=relaxed,
        ):
            return False
    key = coord_key(poi.coordinates)
    if key in seen_coords:
        return False
    seen_ids.add(poi.poi_id)
    seen_coords.add(key)
    seen_names.add(name_key)
    collected.append(poi)
    return True


def merge_poi_pools(
    pools: list[list[PoiPoint]],
    *,
    center: GeoPoint,
    city: str,
    max_items: int = 150,
    pool_target: int | None = None,
) -> list[PoiPoint]:
    target = pool_target if pool_target is not None else max_items
    candidates: list[PoiPoint] = []
    for pool in pools:
        candidates.extend(pool)

    collected: list[PoiPoint] = []
    seen_ids: set[str] = set()
    seen_coords: set[str] = set()
    seen_names: set[str] = set()

    for poi in candidates:
        if len(collected) >= max_items:
            break
        _try_merge_poi(
            collected,
            seen_ids,
            seen_coords,
            seen_names,
            poi,
            center=center,
            city=city,
            relax_wikidata_conflict=False,
        )

    if len(collected) < target:
        for poi in candidates:
            if len(collected) >= max_items:
                break
            if poi.poi_id in seen_ids:
                continue
            _try_merge_poi(
                collected,
                seen_ids,
                seen_coords,
                seen_names,
                poi,
                center=center,
                city=city,
                relax_wikidata_conflict=True,
            )

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
        landmark = 1.0 if is_leisure_route_poi(poi, city_hint=city) else 0.0
        return (boost + match, landmark, 1.0 if poi.address else 0.0, poi.name)

    ordered = sorted(pool, key=rank_key, reverse=True)
    return ordered[:limit]
