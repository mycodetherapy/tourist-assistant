"""Модель предпочтений и строка search_context для веб-поиска и промптов."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from models.routes import LeisureTag


class TripPreferences(BaseModel):
    """Результат опросника перед планированием программы."""

    pace: Literal["relaxed", "moderate", "packed"] = Field(
        ...,
        description="Темп поездки",
    )
    budget: Literal["economy", "medium", "unlimited"] = Field(
        ...,
        description="Бюджет на билеты и питание",
    )
    leisure_categories: list[LeisureTag] = Field(
        default_factory=list,
        description="Категории досуга для поиска на Яндекс.Картах",
    )
    interests: list[str] = Field(
        default_factory=list,
        description="Устарело: свободные интересы (миграция профиля)",
    )
    cuisine: str = Field(default="", description="Предпочтения по кухне")
    min_restaurant_rating: float = Field(
        default=4.0,
        ge=1.0,
        le=5.0,
        description="Минимальный рейтинг ресторанов",
    )
    transport_preference: Literal["metro", "taxi", "walking", "mixed"] = Field(
        ...,
        description="Как передвигаться по городу",
    )
    travel_party: Literal["solo", "couple", "family", "friends"] = Field(
        ...,
        description="Состав группы",
    )
    special_notes: str = Field(
        default="",
        description="Дополнительные пожелания",
    )

    @model_validator(mode="before")
    @classmethod
    def fill_missing_fields(cls, data: Any) -> Any:
        """Старые записи в SQLite и null из веб-формы (InputNumber)."""
        if not isinstance(data, dict):
            return data
        defaults: dict[str, Any] = {
            "pace": "moderate",
            "budget": "medium",
            "transport_preference": "mixed",
            "travel_party": "couple",
            "interests": [],
            "cuisine": "",
            "special_notes": "",
            "min_restaurant_rating": 4.0,
        }
        merged = {**defaults, **data}
        rating = merged.get("min_restaurant_rating")
        if rating is None or rating == "":
            merged["min_restaurant_rating"] = 4.0
        from search.yandex.leisure_tags import normalize_leisure_categories

        raw_cats = merged.get("leisure_categories")
        if not raw_cats and merged.get("interests"):
            blob = " ".join(str(x) for x in merged["interests"]).lower()
            inferred: list[str] = ["landmarks"]
            if "муз" in blob:
                inferred.append("museums")
            if "выстав" in blob:
                inferred.append("exhibitions")
            if "галер" in blob:
                inferred.append("galleries")
            if "театр" in blob:
                inferred.append("theaters")
            if "парк" in blob:
                inferred.append("parks")
            raw_cats = inferred
        merged["leisure_categories"] = normalize_leisure_categories(
            raw_cats if isinstance(raw_cats, list) else None
        )
        return merged


_PACE_RU = {
    "relaxed": "спокойный темп, 1–2 объекта в день",
    "moderate": "умеренный темп, 2–3 объекта в день",
    "packed": "насыщенный темп, максимум мероприятий",
}

_BUDGET_RU = {
    "economy": "эконом, недорогие варианты",
    "medium": "средний бюджет",
    "unlimited": "без жёстких ограничений по цене",
}

_TRANSPORT_RU = {
    "metro": "метро и общественный транспорт",
    "taxi": "такси и каршеринг",
    "walking": "пешие прогулки",
    "mixed": "метро + пешком",
}

_PARTY_RU = {
    "solo": "один",
    "couple": "пара",
    "family": "с детьми",
    "friends": "компания друзей",
}


def build_search_context(preferences: TripPreferences) -> str:
    """
    Сжатый контекст для дополнения поисковых запросов и системного промпта.
    """
    parts: list[str] = [
        _PACE_RU[preferences.pace],
        _BUDGET_RU[preferences.budget],
        _TRANSPORT_RU[preferences.transport_preference],
        f"группа: {_PARTY_RU[preferences.travel_party]}",
    ]
    if preferences.leisure_categories:
        from search.yandex.leisure_tags import TAG_SPECS

        labels = [TAG_SPECS[t].label_ru for t in preferences.leisure_categories if t in TAG_SPECS]
        if labels:
            parts.append("досуг: " + ", ".join(labels))
    elif preferences.interests:
        parts.append("интересы: " + ", ".join(preferences.interests))
    if preferences.cuisine.strip():
        parts.append(f"кухня: {preferences.cuisine.strip()}")
    parts.append(f"рестораны от {preferences.min_restaurant_rating} звёзд/рейтинга")
    if preferences.special_notes.strip():
        parts.append(preferences.special_notes.strip()[:200])
    return "; ".join(parts)


def budget_query_suffix(budget: str) -> str:
    """Короткий суффикс для запросов билетов и ресторанов."""
    if budget == "economy":
        return "недорого бюджет"
    if budget == "unlimited":
        return "премиум"
    return ""


def interests_query_suffix(interests: list[str]) -> str:
    """Ключевые слова для афиши и музеев."""
    if not interests:
        return ""
    return " ".join(interests[:5])


def restaurant_rating_suffix(rating: float) -> str:
    """Суффикс для поиска ресторанов."""
    if rating >= 4.5:
        return f"рейтинг от {rating}"
    return "лучшие отзывы"
