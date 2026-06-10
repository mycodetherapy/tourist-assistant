"""Коды городов для Tutu (жд/автобус) и РЖД (станции в URL)."""

from __future__ import annotations

import math
from functools import lru_cache

from search.city_codes import normalize_city_name

# Автобус в critic и deep links — только для относительно коротких маршрутов.
BUS_MAX_ROUTE_KM = 650

# Имена в path www.tutu.ru/poezda/{From}/{To}/
_TUTU_TRAIN_NAME: dict[str, str] = {
    "москва": "Moskva",
    "санкт-петербург": "Sankt-Peterburg",
    "петербург": "Sankt-Peterburg",
    "питер": "Sankt-Peterburg",
    "саратов": "Saratov",
    "казань": "Kazan",
    "нижний новгород": "Nizhniy_Novgorod",
    "екатеринбург": "Ekaterinburg",
    "новосибирск": "Novosibirsk",
    "самара": "Samara",
    "воронеж": "Voronezh",
    "краснодар": "Krasnodar",
    "сочи": "Sochi",
    "ростов-на-дону": "Rostov",
    "уфа": "Ufa",
    "пермь": "Perm",
    "волгоград": "Volgograd",
    "тюмень": "Tyumen",
    "калининград": "Kaliningrad",
    "владивосток": "Vladivostok",
    "иркутск": "Irkutsk",
    "ярославль": "Yaroslavl",
    "тверь": "Tver",
    "курск": "Kursk",
    "белгород": "Belgorod",
    "пенза": "Penza",
    "ульяновск": "Ulyanovsk",
    "челябинск": "Chelyabinsk",
    "омск": "Omsk",
    "красноярск": "Krasnoyarsk",
    "сыктывкар": "Syktyvkar",
    "йошкар-ола": "Yoshkar-Ola",
    "чебоксары": "Cheboksary",
    "саранск": "Saransk",
}

# Коды узлов ticket.rzd.ru (только проверенные пары; иначе ссылка РЖД не строится)
_RZD_STATION: dict[str, str] = {
    "саратов": "5a13ba86340c745ca1e7eb03",
    "москва": "5a323c29340c7441a0a556bb",
}


def _lookup(mapping: dict[str, str], city: str) -> str | None:
    key = normalize_city_name(city)
    if key in mapping:
        return mapping[key]
    for name, value in mapping.items():
        if name in key or key in name:
            return value
    return None


def _lookup_bus(city: str) -> tuple[str, str] | None:
    from search.providers.tutu_bus import resolve_tutu_bus_city

    return resolve_tutu_bus_city(city)


def city_to_tutu_train_name(city: str) -> str | None:
    return _lookup(_TUTU_TRAIN_NAME, city)


def city_to_rzd_code(city: str) -> str | None:
    return _lookup(_RZD_STATION, city)


def city_to_tutu_bus(city: str) -> tuple[str, str] | None:
    """(gorod_Segment, numeric_id) или None."""
    return _lookup_bus(city)


def ground_transport_available(origin: str, destination: str) -> bool:
    """Жд/автобус deep links возможны только для пар городов из справочника Tutu/РЖД."""
    return (
        city_to_tutu_train_name(origin) is not None
        and city_to_tutu_train_name(destination) is not None
    )


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * radius_km * math.asin(math.sqrt(a))


haversine_km = _haversine_km


@lru_cache(maxsize=256)
def city_pair_distance_km(origin: str, destination: str) -> float | None:
    """Расстояние между центрами городов (Nominatim), км."""
    from search.osm.nominatim import resolve_city_center

    a = resolve_city_center(origin)
    b = resolve_city_center(destination)
    if a is None or b is None:
        return None
    return _haversine_km(a.lat, a.lon, b.lat, b.lon)


def bus_ticket_required(origin: str, destination: str) -> bool:
    """Автобус имеет смысл только на коротких внутренних маршрутах."""
    if not ground_transport_available(origin, destination):
        return False
    distance = city_pair_distance_km(origin, destination)
    if distance is None:
        return False
    return distance <= BUS_MAX_ROUTE_KM


def required_ticket_markers(origin: str, destination: str) -> tuple[str, ...]:
    """Подстроки для проверки блоков билетов (critic, garbage tickets)."""
    from search.airport_routing import avia_ticket_offered

    markers: list[str] = []
    if avia_ticket_offered(origin, destination):
        markers.append("самол")
    if ground_transport_available(origin, destination):
        markers.append("поезд")
        if bus_ticket_required(origin, destination):
            markers.append("автобус")
    return tuple(markers)
