"""Модель предпочтений и строка search_context для веб-поиска и промптов."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


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
    interests: list[str] = Field(
        default_factory=list,
        description="Интересы: музеи, театр, архитектура, еда и т.д.",
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
    if preferences.interests:
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
