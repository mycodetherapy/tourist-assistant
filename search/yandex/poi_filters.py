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


_EMBANKMENT_STREET_RE = re.compile(
    r"(верхне|нижне)?-?набережная\s+улица|набережная\s+улица",
    re.IGNORECASE,
)
_STREET_PREFIX_RE = re.compile(
    r"^(улица|ул\.?|пер\.?|переулок|пр-т|проспект|шоссе|бульвар)\s+",
    re.IGNORECASE,
)
_HOUSE_SUFFIX_RE = re.compile(r",\s*\d", re.IGNORECASE)


def is_generic_street_name(name: str) -> bool:
    """Протяжённые улицы/адреса — не точки маршрута."""
    n = _normalize_name(name)
    if _STREET_PREFIX_RE.match(n):
        return True
    if _EMBANKMENT_STREET_RE.search(n):
        return True
    if _HOUSE_SUFFIX_RE.search(n):
        return True
    if n.endswith(" улица") or n.endswith(" ул"):
        return True
    return False


def is_city_only_name(name: str, *, city_hint: str = "") -> bool:
    """Только название города — не точка маршрута."""
    n = _normalize_name(name)
    if not n:
        return True
    if city_hint and n == _normalize_name(city_hint):
        return True
    return n in {"кострома", "москва", "санкт-петербург", "спб", "казань", "сочи"}


def is_landmark_poi_name(name: str, *, city_hint: str = "") -> bool:
    """Конкретная локация: площадь, храм, музей — не абстрактная улица."""
    if is_city_only_name(name, city_hint=city_hint):
        return False
    if not is_acceptable_place_name(name, city_hint=city_hint):
        return False
    if is_generic_street_name(name):
        return False
    return looks_like_leisure_poi(name)


def route_name_key(name: str) -> str:
    """Ключ для дедупликации подписей на маршруте (улица X ≈ X)."""
    n = _normalize_name(name)
    n = re.sub(r",.*$", "", n).strip()
    for prefix in (
        "улица ",
        "ул ",
        "ул. ",
        "переулок ",
        "пер. ",
        "проспект ",
        "пр-т ",
        "пр. ",
        "набережная ",
        "площадь ",
        "шоссе ",
        "бульвар ",
        "наб. ",
    ):
        if n.startswith(prefix):
            n = n[len(prefix) :].lstrip()
            break
    return n.strip()


def poi_name_conflict(
    name_a: str,
    coords_a: GeoPoint,
    name_b: str,
    coords_b: GeoPoint,
) -> bool:
    """Одинаковые или слишком близкие подписи на маршруте."""
    ka, kb = route_name_key(name_a), route_name_key(name_b)
    if ka == kb:
        return True
    if haversine_km(coords_a, coords_b) > 0.35:
        return False
    shared = set(ka.split()) & set(kb.split())
    return any(len(word) >= 4 for word in shared)


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
    if is_generic_street_name(cleaned):
        return False
    if is_city_only_name(cleaned, city_hint=city_hint):
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
    if kind == "street":
        return False
    if kind in ("vegetation", "hydro", "house", "other"):
        return is_landmark_poi_name(name, city_hint=city_hint)
    return is_landmark_poi_name(name, city_hint=city_hint)


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
