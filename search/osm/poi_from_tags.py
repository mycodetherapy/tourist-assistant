"""OSM/Wikidata → PoiPoint."""

from __future__ import annotations

import hashlib
import re

from models.routes import GeoPoint, LeisureTag, PoiPoint
from search.yandex.leisure_tags import infer_leisure_tag
from search.yandex.poi_filters import (
    is_acceptable_pedestrian_street,
    is_acceptable_place_name,
    is_landmark_poi_name,
    is_pedestrian_street_osm_tags,
    is_temple_osm_tags,
)

_WIKIDATA_COORD_RE = re.compile(r"Point\(([-\d.]+)\s+([-\d.]+)\)")
_LOW_PRIORITY_WD_NAME_RE = re.compile(
    r"^(?:дом на|жилой дом|каменная лавка|жилое здание|административное здание)",
    re.IGNORECASE,
)


def _stable_id(prefix: str, name: str, coords: GeoPoint) -> str:
    raw = f"{name}:{coords.lon:.5f}:{coords.lat:.5f}"
    return f"{prefix}_{hashlib.sha1(raw.encode()).hexdigest()[:10]}"


def _maps_url(coords: GeoPoint) -> str:
    return f"https://yandex.ru/maps/?pt={coords.lon},{coords.lat}&z=16"


def _pick_name(tags: dict[str, str], *, city_hint: str = "") -> str:
    for key in (
        "name:ru",
        "name",
        "name:en",
        "name:tr",
        "int_name",
        "official_name",
        "alt_name:ru",
        "alt_name",
    ):
        value = str(tags.get(key) or "").strip()
        if value:
            return value
    return ""


def is_tagged_leisure_osm(tags: dict[str, str]) -> bool:
    """OSM-элемент уже помечен как leisure/tourism — не требуем русских ключевых слов в name."""
    if is_pedestrian_street_osm_tags(tags) or is_temple_osm_tags(tags):
        return True
    tourism = str(tags.get("tourism") or "").lower()
    historic = str(tags.get("historic") or "").lower()
    leisure = str(tags.get("leisure") or "").lower()
    amenity = str(tags.get("amenity") or "").lower()
    if tourism:
        return True
    if historic:
        return True
    if leisure in {"park", "garden", "nature_reserve", "pedestrian_area"}:
        return True
    if amenity in {
        "museum",
        "theatre",
        "arts_centre",
        "planetarium",
        "place_of_worship",
        "monastery",
    }:
        return True
    if str(tags.get("man_made") or "").lower() == "monument":
        return True
    if str(tags.get("building") or "").lower() in {
        "cathedral",
        "church",
        "chapel",
        "mosque",
        "synagogue",
        "monastery",
        "temple",
    }:
        return True
    return False


def infer_tag_from_osm_tags(tags: dict[str, str]) -> LeisureTag:
    if is_pedestrian_street_osm_tags(tags):
        return "pedestrian_streets"
    if is_temple_osm_tags(tags):
        return "temples"
    tourism = str(tags.get("tourism") or "").lower()
    historic = str(tags.get("historic") or "").lower()
    leisure = str(tags.get("leisure") or "").lower()
    amenity = str(tags.get("amenity") or "").lower()

    if tourism in {"museum", "gallery", "artwork"} or amenity in {
        "museum",
        "arts_centre",
        "theatre",
        "planetarium",
    }:
        return "museums"
    if historic in {"monument", "memorial", "statue", "wayside_shrine"}:
        return "monuments"
    if leisure in {"park", "garden", "nature_reserve"} or tourism == "theme_park":
        return "parks"
    if "набереж" in _pick_name(tags).lower():
        return "embankments"
    if tourism in {"attraction", "viewpoint", "yes"}:
        return "landmarks"
    return infer_leisure_tag(_pick_name(tags))


def osm_element_to_poi(
    element: dict,
    *,
    city_hint: str = "",
) -> PoiPoint | None:
    tags = element.get("tags") or {}
    if not isinstance(tags, dict):
        return None
    tags_str = {str(k): str(v) for k, v in tags.items()}
    name = _pick_name(tags_str, city_hint=city_hint)
    if not name:
        return None
    if is_pedestrian_street_osm_tags(tags_str):
        if not is_acceptable_pedestrian_street(name, city_hint=city_hint):
            return None
    elif is_temple_osm_tags(tags_str) or is_tagged_leisure_osm(tags_str):
        if not is_acceptable_place_name(name, city_hint=city_hint):
            return None
    elif not is_landmark_poi_name(name, city_hint=city_hint):
        return None
    lat = lon = None
    if element.get("type") == "node":
        lat, lon = element.get("lat"), element.get("lon")
    else:
        center = element.get("center") or {}
        lat, lon = center.get("lat"), center.get("lon")
    if lat is None or lon is None:
        return None
    try:
        coords = GeoPoint(lon=float(lon), lat=float(lat))
    except (TypeError, ValueError):
        return None
    el_type = str(element.get("type") or "node")
    el_id = element.get("id")
    poi_id = f"osm_{el_type}_{el_id}" if el_id is not None else _stable_id("osm", name, coords)
    tag = infer_tag_from_osm_tags(tags_str)
    address = str(tags_str.get("addr:full") or tags_str.get("addr:street") or "").strip()
    return PoiPoint(
        poi_id=poi_id,
        tag=tag,
        name=name,
        coordinates=coords,
        maps_url=_maps_url(coords),
        rating=None,
        address=address,
    )


def wikidata_row_to_poi(
    *,
    qid: str,
    name: str,
    coord_literal: str,
    city_hint: str = "",
) -> PoiPoint | None:
    name = name.strip()
    if _LOW_PRIORITY_WD_NAME_RE.search(name):
        return None
    if not name or not is_acceptable_place_name(name, city_hint=city_hint):
        return None
    match = _WIKIDATA_COORD_RE.search(coord_literal or "")
    if not match:
        return None
    try:
        lon, lat = float(match.group(1)), float(match.group(2))
        coords = GeoPoint(lon=lon, lat=lat)
    except (TypeError, ValueError):
        return None
    poi_id = qid if qid.startswith("Q") else f"wikidata_{qid}"
    return PoiPoint(
        poi_id=poi_id,
        tag=infer_leisure_tag(name),
        name=name,
        coordinates=coords,
        maps_url=_maps_url(coords),
        rating=None,
        address="",
    )
