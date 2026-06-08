"""Парсинг ответов Geocoder / GeoJSON в PoiPoint / DiningOption."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from models.routes import DiningOption, GeoPoint, LeisureTag, PoiPoint

_ORG_ID_RE = re.compile(r"/org/[^/]+/(\d+)")


def _stable_id(prefix: str, name: str, coords: GeoPoint) -> str:
    raw = f"{name}:{coords.lon:.5f}:{coords.lat:.5f}"
    return f"{prefix}_{hashlib.sha1(raw.encode()).hexdigest()[:10]}"


def _extract_org_id(url: str, name: str, coords: GeoPoint, prefix: str) -> str:
    match = _ORG_ID_RE.search(url or "")
    if match:
        return match.group(1)
    return _stable_id(prefix, name, coords)


def _coords_from_feature(feature: dict[str, Any]) -> GeoPoint | None:
    geometry = feature.get("geometry") or {}
    coords = geometry.get("coordinates")
    if not isinstance(coords, list) or len(coords) < 2:
        return None
    try:
        lon, lat = float(coords[0]), float(coords[1])
        return GeoPoint(lon=lon, lat=lat)
    except (TypeError, ValueError):
        return None


def feature_to_poi(feature: dict[str, Any], *, tag: LeisureTag) -> PoiPoint | None:
    props = feature.get("properties") or {}
    meta = props.get("CompanyMetaData") or {}
    name = str(meta.get("name") or props.get("name") or "").strip()
    if not name:
        return None
    coords = _coords_from_feature(feature)
    if coords is None:
        return None
    url = str(meta.get("url") or props.get("uri") or "").strip()
    if not url:
        url = f"https://yandex.ru/maps/?pt={coords.lon},{coords.lat}&z=16"
    poi_id = _extract_org_id(url, name, coords, tag)
    rating_raw = meta.get("rating")
    rating: float | None = None
    if isinstance(rating_raw, dict):
        try:
            rating = float(rating_raw.get("value"))
        except (TypeError, ValueError):
            rating = None
    address = str(meta.get("address") or props.get("description") or "").strip()
    return PoiPoint(
        poi_id=poi_id,
        tag=tag,
        name=name,
        coordinates=coords,
        maps_url=url,
        rating=rating,
        address=address,
    )


def feature_to_dining(
    feature: dict[str, Any],
    *,
    anchor_poi_id: str,
) -> DiningOption | None:
    props = feature.get("properties") or {}
    meta = props.get("CompanyMetaData") or {}
    name = str(meta.get("name") or props.get("name") or "").strip()
    if not name:
        return None
    coords = _coords_from_feature(feature)
    if coords is None:
        return None
    url = str(meta.get("url") or props.get("uri") or "").strip()
    if not url:
        url = f"https://yandex.ru/maps/?pt={coords.lon},{coords.lat}&z=17"
    poi_id = _extract_org_id(url, name, coords, f"food_{anchor_poi_id[:8]}")
    rating_raw = meta.get("rating")
    rating: float | None = None
    if isinstance(rating_raw, dict):
        try:
            rating = float(rating_raw.get("value"))
        except (TypeError, ValueError):
            rating = None
    return DiningOption(
        poi_id=poi_id,
        anchor_poi_id=anchor_poi_id,
        name=name,
        coordinates=coords,
        maps_url=url,
        rating=rating,
    )
