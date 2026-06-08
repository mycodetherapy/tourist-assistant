"""Фиксированные теги досуга → поисковые запросы Яндекс.Карт."""

from __future__ import annotations

from dataclasses import dataclass

from models.routes import LeisureTag

_DEFAULT_TAG: LeisureTag = "landmarks"

_ALL_TAGS: tuple[LeisureTag, ...] = (
    "landmarks",
    "museums",
    "exhibitions",
    "galleries",
    "philharmonic",
    "theaters",
    "parks",
)


@dataclass(frozen=True)
class LeisureTagSpec:
    key: LeisureTag
    label_ru: str
    search_query: str
    required: bool = False


TAG_SPECS: dict[LeisureTag, LeisureTagSpec] = {
    "landmarks": LeisureTagSpec(
        "landmarks", "Достопримечательности", "достопримечательность", required=True
    ),
    "museums": LeisureTagSpec("museums", "Музеи", "музей"),
    "exhibitions": LeisureTagSpec("exhibitions", "Выставки", "выставочный зал"),
    "galleries": LeisureTagSpec("galleries", "Галереи", "художественная галерея"),
    "philharmonic": LeisureTagSpec("philharmonic", "Филармонии", "филармония"),
    "theaters": LeisureTagSpec("theaters", "Театры", "театр"),
    "parks": LeisureTagSpec("parks", "Парки", "парк"),
}


def normalize_leisure_categories(raw: list[str] | None) -> list[LeisureTag]:
    """Всегда включает landmarks; неизвестные теги отбрасывает."""
    if not raw:
        return [_DEFAULT_TAG]
    out: list[LeisureTag] = []
    for item in raw:
        key = str(item).strip().lower()
        if key in TAG_SPECS and key not in out:
            out.append(key)  # type: ignore[arg-type]
    if _DEFAULT_TAG not in out:
        out.insert(0, _DEFAULT_TAG)
    return out


def search_text_for_tag(tag: LeisureTag, city: str) -> str:
    spec = TAG_SPECS[tag]
    return f"{spec.search_query} {city}"


def geocode_queries_for_tag(tag: LeisureTag, city: str) -> list[str]:
    """Несколько запросов в HTTP Геокодер (без платного Search API)."""
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
            f"набережная, {city}, Россия",
        ],
        "museums": [
            f"государственный музей, {city}, Россия",
            f"художественный музей, {city}, Россия",
        ],
        "galleries": [
            f"художественная галерея, {city}, Россия",
        ],
        "theaters": [f"театр, {city}, Россия"],
        "parks": [f"парк культуры, {city}, Россия", f"сквер, {city}, Россия"],
        "philharmonic": [f"филармония, {city}, Россия"],
        "exhibitions": [f"выставочный центр, {city}, Россия"],
    }
    for item in extras.get(tag, []):
        if item not in queries:
            queries.append(item)
    return queries


def leisure_pool_limit(pace: str) -> int:
    if pace == "relaxed":
        return 8
    if pace == "packed":
        return 20
    return 14


def dining_per_anchor_limit(pace: str) -> int:
    if pace == "relaxed":
        return 3
    if pace == "packed":
        return 5
    return 4
