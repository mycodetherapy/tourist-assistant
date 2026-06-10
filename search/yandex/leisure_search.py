"""Поиск мест досуга: Wikidata + веб-discovery; Overpass опционален."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass

from models.routes import GeoPoint, LeisureTag, PoiPoint
from search.osm.nominatim import fetch_nominatim_embankments, resolve_city_center
from search.osm.overpass import fetch_overpass_leisure
from search.poi_collect import merge_poi_pools, rank_leisure_pool
from search.poi_match import match_names_to_pool, strong_match_ids
from search.wikidata.places import fetch_wikidata_leisure
from search.yandex.leisure_tags import leisure_search_pool_limit


def _use_wikidata() -> bool:
    return os.getenv("POI_USE_WIKIDATA", "true").lower() in {"1", "true", "yes"}


def _use_discovery() -> bool:
    return os.getenv("POI_USE_DISCOVERY", "true").lower() in {"1", "true", "yes"}


def _use_overpass() -> bool:
    # Overpass отключён по умолчанию: публичные инстансы из РФ отвечают слишком долго.
    return os.getenv("POI_USE_OVERPASS", "false").lower() in {"1", "true", "yes"}


@dataclass
class LeisureSearchResult:
    points: list[PoiPoint]
    landmark_discovery: dict | None = None
    poi_sources: dict | None = None


def search_leisure_points(
    *,
    city: str,
    categories: list[LeisureTag],
    pace: str = "moderate",
) -> LeisureSearchResult:
    del categories  # теги выводятся из OSM/Wikidata, не из шаблонов Geocoder
    del pace  # темп влияет на сборку A/B/C, не на размер поискового пула
    limit = leisure_search_pool_limit()
    center = resolve_city_center(city)
    if center is None:
        return LeisureSearchResult(points=_demo_leisure(city, limit))

    geo_center = GeoPoint(lon=center.lon, lat=center.lat)
    osm_points: list[PoiPoint] = []
    wikidata_points: list[PoiPoint] = []
    embankment_points: list[PoiPoint] = []
    fetch_osm = _use_overpass()
    fetch_wd = _use_wikidata()

    if fetch_wd:
        wikidata_points = fetch_wikidata_leisure(
            city,
            center,
            wikidata_id=center.wikidata_id,
            pool_target=limit,
        )
    if fetch_osm:
        osm_points = fetch_overpass_leisure(
            city, center, max_elements=max(limit * 4, 40)
        )
    # Набережные уже в Wikidata SPARQL; Nominatim — только без Wikidata.
    embankment_points: list[PoiPoint] = []
    if not fetch_wd:
        embankment_points = fetch_nominatim_embankments(city, center, max_items=4)

    pool = merge_poi_pools(
        [osm_points, wikidata_points, embankment_points],
        center=geo_center,
        city=city,
        max_items=max(limit * 2, 80),
        pool_target=limit,
    )

    discovery_trace: dict | None = None
    boosted_ids: set[str] = set()
    match_scores: dict[str, float] = {}

    if _use_discovery() and pool:
        from search.yandex.landmark_discovery import run_landmark_discovery

        names, trace = run_landmark_discovery(city)
        matches = match_names_to_pool(names, pool)
        trace.matched_pois = [
            {
                "discovery_name": m.discovery_name,
                "poi_id": m.poi_id,
                "poi_name": m.poi_name,
                "score": m.score,
            }
            for m in matches
        ]
        boosted_ids = strong_match_ids(matches)
        match_scores = {m.poi_id: m.score for m in matches}
        discovery_trace = trace.to_dict()

    ranked = rank_leisure_pool(
        pool,
        boosted_poi_ids=boosted_ids,
        match_scores=match_scores,
        city=city,
        limit=max(limit, len(pool)),
    )

    if not ranked:
        return LeisureSearchResult(
            points=_demo_leisure(city, limit, lon=center.lon, lat=center.lat),
            poi_sources={
                "center": "nominatim",
                "osm_count": len(osm_points),
                "wikidata_count": len(wikidata_points),
                "embankment_count": len(embankment_points),
                "pool_count": len(pool),
            },
        )

    return LeisureSearchResult(
        points=ranked,
        landmark_discovery=discovery_trace,
        poi_sources={
            "center": "nominatim",
            "osm_count": len(osm_points),
            "wikidata_count": len(wikidata_points),
            "embankment_count": len(embankment_points),
            "pool_count": len(pool),
            "matched_count": len(boosted_ids),
        },
    )


def _demo_leisure(
    city: str,
    limit: int,
    *,
    lon: float = 37.62,
    lat: float = 55.75,
    spn_lon: float = 0.1,
    spn_lat: float = 0.08,
) -> list[PoiPoint]:
    """Демо-POI когда open-data не вернула места."""
    from search.yandex.leisure_tags import TAG_SPECS, default_geocoder_tags

    categories = default_geocoder_tags()
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
        coords = GeoPoint(lon=point_lon, lat=point_lat)
        poi_id = f"demo_{tag}_{index}"
        collected.append(
            PoiPoint(
                poi_id=poi_id,
                tag=tag,
                name=name,
                coordinates=coords,
                maps_url=f"https://yandex.ru/maps/org/demo_{tag}/{index}",
                rating=4.5 - (index % 5) * 0.1,
                address=city,
            )
        )
        seen_ids.add(poi_id)
        index += 1
    return collected
