"""Фильтры POI: без транспортных узлов и дальних точек от центра."""

from __future__ import annotations

import math
import re

from models.routes import GeoPoint, PoiPoint

# Транспорт и инфраструктура — не точки пешего маршрута по городу
_TRANSPORT_NAME_RE = re.compile(
    r"(аэропорт|аэроп\.?|вокзал|станци[яи]\s|станция\b|причал|порт\b|ж/д|жд\b|"
    r"аэровокзал|автовокзал|перрон|аэро|метро\b|метрополитен|"
    r"railway|airport|train\s+station)",
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
    "памятн",
    "монумент",
    "стел",
    "усадьб",
    "дворец",
    "набереж",
    "сквер",
    "бульвар",
    "пешеходн",
    "покровск",
    "бауман",
    "променад",
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
    "мечеть",
    "костел",
    "сад ",
    "сад,",
    # EN/TR подписи в OSM/Wikidata за рубежом
    "museum",
    "gallery",
    "park",
    "mosque",
    "palace",
    "church",
    "cathedral",
    "monument",
    "mosque",
    "square",
    "basilica",
    "cistern",
    "bazaar",
    "tower",
    "fortress",
    "synagogue",
    "theatre",
    "theater",
    "camii",
    "cami",
    "kilise",
    "saray",
    "cami-i",
    "tomb",
    "fountain",
    "hamam",
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


def walkable_radius_km(city: str = "") -> float:
    """Радиус пулa POI от центра; для крупных зарубежных городов — шире."""
    from search.city_codes import is_foreign_destination

    if city and is_foreign_destination(city):
        return 7.5
    return 4.5


def is_city_only_name(name: str, *, city_hint: str = "") -> bool:
    """Только название города — не точка маршрута."""
    n = _normalize_name(name)
    if not n:
        return True
    if city_hint and n == _normalize_name(city_hint):
        return True
    return n in {
        "кострома",
        "москва",
        "санкт-петербург",
        "спб",
        "казань",
        "сочи",
        "стамбул",
        "istanbul",
    }


def is_pedestrian_street_osm_tags(tags: dict[str, str]) -> bool:
    """OSM-теги пешеходной зоны с именованным объектом."""
    highway = str(tags.get("highway") or "").lower()
    if highway == "pedestrian" and str(tags.get("name") or "").strip():
        return True
    if str(tags.get("place") or "").lower() == "square" and str(tags.get("name") or "").strip():
        return True
    if str(tags.get("leisure") or "").lower() == "pedestrian_area":
        return True
    return False


def is_temple_osm_tags(tags: dict[str, str]) -> bool:
    """OSM-теги храма, собора или монастыря."""
    historic = str(tags.get("historic") or "").lower()
    building = str(tags.get("building") or "").lower()
    amenity = str(tags.get("amenity") or "").lower()
    if historic in {"church", "monastery", "cathedral", "wayside_shrine"}:
        return True
    if building in {
        "cathedral",
        "church",
        "chapel",
        "mosque",
        "synagogue",
        "monastery",
        "temple",
    }:
        return True
    if amenity in {"place_of_worship", "monastery"}:
        return True
    return False


def is_acceptable_pedestrian_street(name: str, *, city_hint: str = "") -> bool:
    """Именованная пешеходная улица/бульвар — допускаем «улица X» в названии."""
    cleaned = name.strip()
    if not cleaned or len(cleaned) < 3:
        return False
    if city_hint and _normalize_name(cleaned) == _normalize_name(city_hint):
        return False
    if is_transport_hub(cleaned):
        return False
    if is_generic_area(cleaned):
        return False
    if _HOUSE_SUFFIX_RE.search(cleaned):
        return False
    return True


def is_leisure_route_poi(poi: PoiPoint, *, city_hint: str = "") -> bool:
    """POI подходит для пешего маршрута (включая пешеходные улицы по тегу)."""
    if poi.tag == "pedestrian_streets":
        return is_acceptable_pedestrian_street(poi.name, city_hint=city_hint)
    if poi.tag == "embankments":
        return is_embankment_poi_name(poi.name, city_hint=city_hint)
    return is_landmark_poi_name(poi.name, city_hint=city_hint)


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


_EMBANKMENT_NAME_RE = re.compile(
    r"набереж|embankment|promenade|waterfront|riverside|river\s+walk|"
    r"ufer|kordon|corso",
    re.IGNORECASE,
)


def is_embankment_poi_name(name: str, *, city_hint: str = "") -> bool:
    """Именованная набережная/променад — точка живописного маршрута."""
    cleaned = name.strip()
    if not cleaned or not _EMBANKMENT_NAME_RE.search(cleaned):
        return False
    if is_city_only_name(cleaned, city_hint=city_hint):
        return False
    if is_transport_hub(cleaned) or is_generic_area(cleaned):
        return False
    if _EMBANKMENT_STREET_RE.search(cleaned):
        return False
    if _HOUSE_SUFFIX_RE.search(cleaned):
        return False
    return True


def wikidata_poi_name_conflict(name_a: str, name_b: str) -> bool:
    """Мягкая дедупликация Wikidata: только одинаковый ключ подписи."""
    return route_name_key(name_a) == route_name_key(name_b)


def poi_name_conflict(
    name_a: str,
    coords_a: GeoPoint,
    name_b: str,
    coords_b: GeoPoint,
    *,
    relaxed: bool = False,
) -> bool:
    """Одинаковые или слишком близкие подписи на маршруте."""
    if relaxed:
        return wikidata_poi_name_conflict(name_a, name_b)
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
        return is_landmark_poi_name(name, city_hint=city_hint)
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
