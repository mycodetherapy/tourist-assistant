"""Коды городов для Tutu (жд/автобус) и РЖД (станции в URL)."""

from __future__ import annotations

from search.city_codes import normalize_city_name

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
}

# gorod_{Name} и numeric id для bus.tutu.ru (проверенные id)
_TUTU_BUS: dict[str, tuple[str, str]] = {
    "москва": ("gorod_Moskva", "1447874"),
    "санкт-петербург": ("gorod_Sankt-Peterburg", "1447874"),
    "петербург": ("gorod_Sankt-Peterburg", "1447874"),
    "саратов": ("gorod_Saratov", "1433947"),
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
    key = normalize_city_name(city)
    if key in _TUTU_BUS:
        return _TUTU_BUS[key]
    for name, value in _TUTU_BUS.items():
        if name in key or key in name:
            return value
    return None


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
