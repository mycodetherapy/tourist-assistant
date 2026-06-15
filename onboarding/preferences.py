"""Модель предпочтений и строка search_context для веб-поиска и промптов."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

FIXED_PACE: Literal["packed"] = "packed"
FIXED_BUDGET: Literal["medium"] = "medium"
FIXED_TRANSPORT: Literal["mixed"] = "mixed"

TRAVEL_PARTY_VALUES = (
    "solo",
    "couple",
    "family",
    "friends",
    "parent_child",
    "family_two",
)

RouteAnchorSource = Literal["address", "coordinates", "map"]


class RouteAnchor(BaseModel):
    """Базовая точка маршрута (отель, квартира, вокзал)."""

    lat: float = Field(..., ge=-90.0, le=90.0)
    lon: float = Field(..., ge=-180.0, le=180.0)
    label: str = Field(default="", max_length=500)
    source: RouteAnchorSource = "map"
    loop_end: bool = Field(
        default=False,
        description="Конечная точка совпадает с базовой (кольцо через anchor)",
    )


class TripPreferences(BaseModel):
    """Результат опросника перед планированием программы."""

    pace: Literal["relaxed", "moderate", "packed"] = Field(
        ...,
        description="Темп поездки (в UI скрыт, по умолчанию packed)",
    )
    budget: Literal["economy", "medium", "unlimited"] = Field(
        ...,
        description="Legacy: не используется в поиске",
    )
    interests: list[str] = Field(
        default_factory=list,
        description="Legacy: не влияет на пул POI",
    )
    cuisine: str = Field(default="", description="Legacy: поиск ресторанов отключён")
    min_restaurant_rating: float = Field(
        default=4.0,
        ge=1.0,
        le=5.0,
        description="Legacy: не используется",
    )
    transport_preference: Literal["metro", "taxi", "walking", "mixed"] = Field(
        ...,
        description="Передвижение (в UI скрыт, по умолчанию mixed)",
    )
    travel_party: Literal[
        "solo",
        "couple",
        "family",
        "friends",
        "parent_child",
        "family_two",
    ] = Field(
        ...,
        description="Состав группы",
    )
    special_notes: str = Field(
        default="",
        description="Legacy: доп. пожелания",
    )
    route_anchor: RouteAnchor | None = Field(
        default=None,
        description="Базовая точка маршрута; null — не задана",
    )

    @model_validator(mode="before")
    @classmethod
    def fill_missing_fields(cls, data: Any) -> Any:
        """Старые записи в SQLite и null из веб-формы (InputNumber)."""
        if not isinstance(data, dict):
            return data
        merged = {
            **{
                "pace": FIXED_PACE,
                "budget": FIXED_BUDGET,
                "transport_preference": FIXED_TRANSPORT,
                "travel_party": "couple",
                "interests": [],
                "cuisine": "",
                "special_notes": "",
                "min_restaurant_rating": 4.0,
            },
            **data,
        }
        merged.pop("leisure_categories", None)
        rating = merged.get("min_restaurant_rating")
        if rating is None or rating == "":
            merged["min_restaurant_rating"] = 4.0
        if merged.get("interests") is None:
            merged["interests"] = []
        return merged


def _parse_route_anchor(raw: Any) -> RouteAnchor | None:
    if raw is None:
        return None
    if isinstance(raw, RouteAnchor):
        return raw
    if isinstance(raw, dict):
        try:
            return RouteAnchor.model_validate(raw)
        except Exception:
            return None
    return None


def normalize_trip_preferences(data: TripPreferences | dict[str, Any]) -> TripPreferences:
    """Скрытые поля фиксированы; из UI — travel_party и route_anchor."""
    if isinstance(data, TripPreferences):
        party = data.travel_party
        route_anchor = data.route_anchor
    else:
        party = str(data.get("travel_party") or "couple")
        route_anchor = _parse_route_anchor(data.get("route_anchor"))
    if party not in TRAVEL_PARTY_VALUES:
        party = "couple"
    return TripPreferences(
        pace=FIXED_PACE,
        budget=FIXED_BUDGET,
        interests=[],
        cuisine="",
        min_restaurant_rating=4.0,
        transport_preference=FIXED_TRANSPORT,
        travel_party=party,  # type: ignore[arg-type]
        special_notes="",
        route_anchor=route_anchor,
    )


def merge_trip_preferences(
    existing: TripPreferences | dict[str, Any] | None,
    update: dict[str, Any],
) -> TripPreferences:
    """Обновляет предпочтения поездки, сохраняя фиксированные поля."""
    base = normalize_trip_preferences(existing or {})
    party = base.travel_party
    if "travel_party" in update:
        candidate = str(update.get("travel_party") or party)
        if candidate in TRAVEL_PARTY_VALUES:
            party = candidate  # type: ignore[assignment]
    route_anchor = base.route_anchor
    if "route_anchor" in update:
        route_anchor = _parse_route_anchor(update.get("route_anchor"))
    return TripPreferences(
        pace=FIXED_PACE,
        budget=FIXED_BUDGET,
        interests=[],
        cuisine="",
        min_restaurant_rating=4.0,
        transport_preference=FIXED_TRANSPORT,
        travel_party=party,
        special_notes="",
        route_anchor=route_anchor,
    )


_PARTY_RU = {
    "solo": "1 взрослый",
    "couple": "2 взрослых",
    "family": "2 взрослых + 1 ребёнок",
    "parent_child": "1 взрослый + 1 ребёнок",
    "family_two": "2 взрослых + 2 ребёнка",
    "friends": "3 взрослых",
}


def build_search_context(preferences: TripPreferences) -> str:
    """Сжатый контекст для промпта planner/writer."""
    prefs = normalize_trip_preferences(preferences)
    return (
        f"группа: {_PARTY_RU[prefs.travel_party]}; "
        "насыщенный темп; метро + пешком"
    )
