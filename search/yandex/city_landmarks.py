"""Известные места города — запасной пул, когда шаблонный Geocoder даёт вокзалы."""

from __future__ import annotations

from dataclasses import dataclass

from models.routes import GeoPoint, LeisureTag

_DEFAULT_WALK_RADIUS_KM = 4.5


@dataclass(frozen=True)
class LandmarkSeed:
    name: str
    tag: LeisureTag
    query: str
    lon: float | None = None
    lat: float | None = None


def _city_key(city: str) -> str:
    return city.lower().strip().replace("ё", "е")


_CITY_SEEDS: dict[str, list[LandmarkSeed]] = {
    "кострома": [
        LandmarkSeed(
            "Сусанинская площадь",
            "landmarks",
            "Сусанинская площадь, Кострома, Россия",
            40.927155,
            57.768072,
        ),
        LandmarkSeed(
            "Богоявленско-Анастасин монастырь",
            "landmarks",
            "Богоявленско-Анастасин монастырь, Кострома, Россия",
            40.9256,
            57.7661,
        ),
        LandmarkSeed(
            "Ипатьевский монастырь",
            "landmarks",
            "Ипатьевский монастырь, Кострома, Россия",
            40.8782,
            57.7781,
        ),
        LandmarkSeed(
            "Пожарная каланча",
            "landmarks",
            "Пожарная каланча, Кострома, Россия",
            40.9263,
            57.7672,
        ),
        LandmarkSeed(
            "Торговые ряды",
            "landmarks",
            "улица Красные Ряды, Кострома, Россия",
            40.925538,
            57.766684,
        ),
        LandmarkSeed(
            "Набережная Волги",
            "landmarks",
            "Набережная улица, Кострома, Россия",
            40.922088,
            57.753649,
        ),
        LandmarkSeed(
            "Костромской дендропарк",
            "parks",
            "Костромской дендропарк",
            40.972564,
            57.820511,
        ),
        LandmarkSeed(
            "Музей деревянного зодчества",
            "museums",
            "Костромская слобода, Кострома, Россия",
            40.9909,
            57.8029,
        ),
    ],
    "москва": [
        LandmarkSeed("Красная площадь", "landmarks", "Красная площадь, Москва, Россия"),
        LandmarkSeed("Государственный исторический музей", "museums", "Государственный исторический музей, Москва"),
        LandmarkSeed("Парк Зарядье", "parks", "Парк Зарядье, Москва"),
        LandmarkSeed("Большой театр", "theaters", "Большой театр, Москва"),
    ],
    "санкт-петербург": [
        LandmarkSeed("Дворцовая площадь", "landmarks", "Дворцовая площадь, Санкт-Петербург"),
        LandmarkSeed("Эрмитаж", "museums", "Государственный Эрмитаж, Санкт-Петербург"),
        LandmarkSeed("Летний сад", "parks", "Летний сад, Санкт-Петербург"),
    ],
}


def seeds_for_city(city: str, categories: list[LeisureTag]) -> list[LandmarkSeed]:
    """Сиды города, отфильтрованные по выбранным категориям досуга."""
    key = _city_key(city)
    pool = _CITY_SEEDS.get(key, [])
    if not pool:
        return generic_center_seeds(city, categories)
    allowed = set(categories)
    return [seed for seed in pool if seed.tag in allowed or seed.tag == "landmarks"]


def generic_center_seeds(city: str, categories: list[LeisureTag]) -> list[LandmarkSeed]:
    """Универсальные запросы по историческому центру."""
    templates: list[tuple[str, LeisureTag, str]] = [
        (f"главная площадь {city}", "landmarks", f"главная площадь, {city}, Россия"),
        (f"исторический центр {city}", "landmarks", f"исторический центр, {city}, Россия"),
        (f"набережная {city}", "landmarks", f"набережная, {city}, Россия"),
        (f"парк культуры {city}", "parks", f"парк культуры, {city}, Россия"),
        (f"художественный музей {city}", "museums", f"художественный музей, {city}, Россия"),
        (f"театр {city}", "theaters", f"театр, {city}, Россия"),
    ]
    allowed = set(categories) | {"landmarks"}
    out: list[LandmarkSeed] = []
    for name, tag, query in templates:
        if tag not in allowed:
            continue
        out.append(LandmarkSeed(name, tag, query))
    return out


def seed_to_feature(seed: LandmarkSeed) -> dict:
    """Feature GeoJSON из сида (координаты из геокодера или запасные)."""
    if seed.lon is None or seed.lat is None:
        raise ValueError("seed without coordinates")
    from urllib.parse import quote

    lon, lat = seed.lon, seed.lat
    maps_url = f"https://yandex.ru/maps/?text={quote(seed.name)}&ll={lon},{lat}&z=16"
    return {
        "geometry": {"coordinates": [lon, lat]},
        "properties": {
            "name": seed.name,
            "description": seed.query,
            "CompanyMetaData": {
                "name": seed.name,
                "address": seed.query,
                "url": maps_url,
            },
        },
    }


def fallback_coords(seed: LandmarkSeed) -> GeoPoint | None:
    if seed.lon is None or seed.lat is None:
        return None
    return GeoPoint(lon=seed.lon, lat=seed.lat)
