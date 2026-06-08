"""Фильтры POI: без транспортных узлов и дальних точек от центра."""

from __future__ import annotations

import math
import re

from models.routes import GeoPoint

# Транспорт и инфраструктура — не точки пешего маршрута по городу
_TRANSPORT_NAME_RE = re.compile(
    r"(аэропорт|вокзал|станци[яи]|причал|порт\b|ж/д|жд\b|"
    r"аэровокзал|автовокзал|перрон|аэро)",
    re.IGNORECASE,
)

_GENERIC_AREA_RE = re.compile(
    r"(район\b|округ\b|область\b|микрорайон|садоводческ|товариществ)",
    re.IGNORECASE,
)

_SKIP_GEO_KINDS = frozenset(
    {
        "country",
        "region",
        "province",
        "area",
        "district",
        "locality",
    }
)

_SKIP_TRANSPORT_KINDS = frozenset(
    {
        "metro",
        "railway",
        "route",
        "station",
        "railway_station",
        "airport",
    }
)

_LEISURE_NAME_HINTS = (
    "муз",
    "галер",
    "театр",
    "парк",
    "филармон",
    "выстав",
    "достопримеч",
    "площад",
    "собор",
    "кремл",
    "заповедник",
    "мемориал",
    "усадьб",
    "дворец",
    "набереж",
    "сквер",
    "бульвар",
    "монаст",
    "колокольн",
    "каланч",
    "ряды",
    "слобод",
    "дендропарк",
    "ресторан",
    "кафе",
    "столовая",
    "бистро",
    "кухня",
    "церков",
    "храм",
    "костел",
    "сад ",
    "сад,",
)


def _normalize_name(name: str) -> str:
    return name.lower().replace("ё", "е").strip()


def is_transport_hub(name: str) -> bool:
    return bool(_TRANSPORT_NAME_RE.search(_normalize_name(name)))


def is_generic_area(name: str) -> bool:
    return bool(_GENERIC_AREA_RE.search(_normalize_name(name)))


def looks_like_leisure_poi(name: str) -> bool:
    lowered = _normalize_name(name)
    return any(hint in lowered for hint in _LEISURE_NAME_HINTS)


def is_acceptable_place_name(name: str, *, city_hint: str = "") -> bool:
    cleaned = name.strip()
    if not cleaned or len(cleaned) < 3:
        return False
    if city_hint and _normalize_name(cleaned) == _normalize_name(city_hint):
        return False
    if is_transport_hub(cleaned):
        return False
    if is_generic_area(cleaned):
        return False
    return True


def is_acceptable_geo_member(member: dict, *, city_hint: str = "") -> bool:
    obj = member.get("GeoObject") or {}
    meta = obj.get("metaDataProperty", {}).get("GeocoderMetaData", {})
    kind = str(meta.get("kind") or "").lower()
    if kind in _SKIP_GEO_KINDS or kind in _SKIP_TRANSPORT_KINDS:
        return False
    name = str(obj.get("name") or "").strip()
    if not is_acceptable_place_name(name, city_hint=city_hint):
        return False
    if not str(obj.get("Point", {}).get("pos", "")):
        return False
    if kind in ("vegetation", "hydro", "street", "house", "other"):
        return looks_like_leisure_poi(name)
    return True


def haversine_km(a: GeoPoint, b: GeoPoint) -> float:
    """Приблизительное расстояние между двумя точками."""
    r = 6371.0
    lat1, lon1 = math.radians(a.lat), math.radians(a.lon)
    lat2, lon2 = math.radians(b.lat), math.radians(b.lon)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    x = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(x))


def within_walkable_radius(
    point: GeoPoint,
    center: GeoPoint,
    *,
    max_km: float = 4.5,
) -> bool:
    return haversine_km(point, center) <= max_km


def coord_key(coords: GeoPoint, *, precision: int = 4) -> str:
    return f"{coords.lon:.{precision}f}:{coords.lat:.{precision}f}"
