"""Теги POI для HTTP Геокодера (без Search API и без выбора пользователем)."""

from __future__ import annotations

from dataclasses import dataclass

from models.routes import LeisureTag

# Теги, по которым Geocoder чаще отдаёт именованные объекты (парки, набережные, музеи).
DEFAULT_GEOCODER_TAGS: tuple[LeisureTag, ...] = (
    "landmarks",
    "parks",
    "museums",
    "monuments",
)


@dataclass(frozen=True)
class LeisureTagSpec:
    key: LeisureTag
    label_ru: str
    search_query: str


TAG_SPECS: dict[LeisureTag, LeisureTagSpec] = {
    "landmarks": LeisureTagSpec("landmarks", "Достопримечательности", "достопримечательность"),
    "parks": LeisureTagSpec("parks", "Парки", "парк"),
    "museums": LeisureTagSpec("museums", "Музеи", "музей"),
    "embankments": LeisureTagSpec("embankments", "Набережные", "набережная"),
    "monuments": LeisureTagSpec("monuments", "Памятники", "памятник"),
    "temples": LeisureTagSpec("temples", "Храмы и монастыри", "храм"),
    "pedestrian_streets": LeisureTagSpec(
        "pedestrian_streets", "Пешеходные улицы", "пешеходная улица"
    ),
    # legacy — только для старых записей в SQLite
    "exhibitions": LeisureTagSpec("exhibitions", "Выставки", "выставочный зал"),
    "galleries": LeisureTagSpec("galleries", "Галереи", "художественная галерея"),
    "philharmonic": LeisureTagSpec("philharmonic", "Филармонии", "филармония"),
    "theaters": LeisureTagSpec("theaters", "Театры", "театр"),
}


def default_geocoder_tags() -> list[LeisureTag]:
    return list(DEFAULT_GEOCODER_TAGS)


def search_text_for_tag(tag: LeisureTag, city: str) -> str:
    spec = TAG_SPECS[tag]
    return f"{spec.search_query} {city}"


def geocode_queries_for_tag(tag: LeisureTag, city: str) -> list[str]:
    """Несколько запросов в HTTP Геокодер."""
    spec = TAG_SPECS[tag]
    q = spec.search_query
    label = spec.label_ru
    queries = [
        f"{q} {city}, Россия",
        f"{label} {city}, Россия",
    ]
    extras: dict[LeisureTag, list[str]] = {
        "landmarks": [
            f"главная площадь, {city}, Россия",
            f"исторический центр, {city}, Россия",
            f"смотровая площадка, {city}, Россия",
        ],
        "parks": [
            f"парк культуры, {city}, Россия",
            f"сквер, {city}, Россия",
            f"ботанический сад, {city}, Россия",
        ],
        "museums": [
            f"государственный музей, {city}, Россия",
            f"художественный музей, {city}, Россия",
            f"краеведческий музей, {city}, Россия",
        ],
        "embankments": [
            f"набережная реки, {city}, Россия",
            f"речная набережная, {city}, Россия",
        ],
        "monuments": [
            f"памятник, {city}, Россия",
            f"монумент, {city}, Россия",
            f"скульптурный парк, {city}, Россия",
        ],
        "temples": [
            f"собор, {city}, Россия",
            f"церковь, {city}, Россия",
            f"монастырь, {city}, Россия",
            f"храм, {city}, Россия",
        ],
        "pedestrian_streets": [
            f"пешеходная улица, {city}, Россия",
            f"пешеходный бульвар, {city}, Россия",
            f"историческая улица, {city}, Россия",
        ],
    }
    for item in extras.get(tag, []):
        if item not in queries:
            queries.append(item)
    return queries


def infer_leisure_tag(name: str) -> LeisureTag:
    """Тег POI по ключевым словам в названии."""
    lowered = name.lower().replace("ё", "е")
    if any(
        h in lowered
        for h in (
            "собор",
            "храм",
            "церк",
            "монаст",
            "часовн",
            "мечет",
            "синагог",
            "костел",
            "базилик",
            "лавр",
        )
    ):
        return "temples"
    if any(
        h in lowered
        for h in ("покровск", "бауман", "пешеходн", "променад", "пешеходная")
    ):
        return "pedestrian_streets"
    if any(h in lowered for h in ("муз", "галер", "выстав", "museum", "gallery")):
        return "museums"
    if "набереж" in lowered:
        return "embankments"
    if any(h in lowered for h in ("парк", "сквер", "сад ", "сад,", "ботаническ")):
        return "parks"
    if any(h in lowered for h in ("памятник", "монумент", "мемориал")):
        return "monuments"
    return "landmarks"


def leisure_pool_limit(pace: str) -> int:
    """Сколько POI может попасть в один маршрут (legacy; см. leisure_search_pool_limit)."""
    if pace == "relaxed":
        return 8
    if pace == "packed":
        return 20
    return 14


def leisure_search_pool_limit() -> int:
    """Целевой размер пула POI (Tier 0 + Tier 1), не зависит от темпа маршрута."""
    from search.wikidata.places import DEFAULT_WIKIDATA_POOL_TARGET

    return DEFAULT_WIKIDATA_POOL_TARGET
