"""Запрос POI из city pack poi.sqlite."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from models.routes import GeoPoint, LeisureTag, PoiPoint
from search.osm.city_pack import is_pack_ready, pack_dir_for_slug
from search.osm.nominatim import CityCenter
from search.yandex.poi_filters import (
    coord_key,
    is_leisure_route_poi,
    poi_name_conflict,
    route_name_key,
    walkable_radius_km,
    within_walkable_radius,
)


def _poi_db_path(slug: str) -> Path:
    from config.city_catalog import get_city_pack_spec

    spec = get_city_pack_spec(slug)
    if spec is not None:
        return spec.poi_db_path
    return pack_dir_for_slug(slug) / "poi.sqlite"


def query_city_poi(
    slug: str,
    *,
    center: CityCenter,
    city: str,
    max_items: int = 120,
    tags: list[LeisureTag] | None = None,
    text_query: str | None = None,
) -> list[PoiPoint]:
    """POI из city pack. tags/text_query — задел под персонализацию (пока опционально)."""
    if not is_pack_ready(slug):
        return []
    db_path = _poi_db_path(slug)
    if not db_path.is_file():
        return []

    geo_center = GeoPoint(lon=center.lon, lat=center.lat)
    radius_km = walkable_radius_km(city)

    sql = "SELECT poi_id, name, lon, lat, leisure_tag, maps_url, address, osm_tags_json FROM poi"
    params: list[object] = []
    clauses: list[str] = []
    if tags:
        placeholders = ",".join("?" for _ in tags)
        clauses.append(f"leisure_tag IN ({placeholders})")
        params.extend(tags)
    if text_query and text_query.strip():
        clauses.append("name LIKE ?")
        params.append(f"%{text_query.strip()}%")
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)

    collected: list[PoiPoint] = []
    seen_ids: set[str] = set()
    seen_coords: set[str] = set()
    seen_names: set[str] = set()

    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    for row in rows:
        poi_id, name, lon, lat, leisure_tag, maps_url, address, _tags_json = row
        try:
            coords = GeoPoint(lon=float(lon), lat=float(lat))
        except (TypeError, ValueError):
            continue
        poi = PoiPoint(
            poi_id=str(poi_id),
            tag=leisure_tag,  # type: ignore[arg-type]
            name=str(name),
            coordinates=coords,
            maps_url=str(maps_url),
            rating=None,
            address=str(address or ""),
        )
        if poi.poi_id in seen_ids:
            continue
        if not is_leisure_route_poi(poi, city_hint=city):
            continue
        name_key = route_name_key(poi.name)
        if name_key in seen_names:
            continue
        for existing in collected:
            if poi_name_conflict(
                poi.name, poi.coordinates, existing.name, existing.coordinates
            ):
                break
        else:
            if not within_walkable_radius(poi.coordinates, geo_center, max_km=radius_km):
                continue
            key = coord_key(poi.coordinates)
            if key in seen_coords:
                continue
            seen_ids.add(poi.poi_id)
            seen_coords.add(key)
            seen_names.add(name_key)
            collected.append(poi)
            if len(collected) >= max_items:
                break

    return collected


def fetch_city_pack_poi(
    slug: str,
    center: CityCenter,
    city: str,
    *,
    max_elements: int = 120,
) -> list[PoiPoint]:
    return query_city_poi(
        slug,
        center=center,
        city=city,
        max_items=max_elements,
    )
