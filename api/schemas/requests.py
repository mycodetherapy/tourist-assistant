"""Тела запросов REST API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from onboarding.preferences import RouteAnchor, TripPreferences

RebuildScope = Literal["full", "tickets", "routes", "lifehacks", "events", "dining"]
ReviewAction = Literal["approve", "save_draft", "rebuild"]
VotableSectionKey = Literal["routes", "route_stops", "lifehacks", "events", "dining"]
ItemVote = Literal[1, -1]


class CreateTripRequest(BaseModel):
    city: str
    dates: str
    origin_city: str = "Москва"
    user_query: str = "Составь культурную программу поездки"
    preferences: TripPreferences
    start_run: bool = True


class StartRunRequest(BaseModel):
    scope: RebuildScope = "full"


class ReviewRequest(BaseModel):
    action: ReviewAction


class AffiliateClickRequest(BaseModel):
    target_url: str = Field(..., min_length=8, max_length=2000)
    provider: str | None = Field(default=None, max_length=64)


class UpdateSettingsRequest(BaseModel):
    llm_api_key: str | None = Field(default=None, max_length=256)
    llm_base_url: str | None = Field(default=None, max_length=512)
    llm_model: str | None = Field(default=None, max_length=128)


class UpdatePreferencesRequest(BaseModel):
    travel_party: (
        Literal["solo", "couple", "family", "friends", "parent_child", "family_two"] | None
    ) = None
    route_anchor: RouteAnchor | None = Field(
        default=None,
        description="null — удалить базовую точку",
    )


class GeocodeRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=500)
    city_hint: str = Field(default="", max_length=128)


class ReverseGeocodeRequest(BaseModel):
    lat: float = Field(..., ge=-90.0, le=90.0)
    lon: float = Field(..., ge=-180.0, le=180.0)
    city_hint: str = Field(default="", max_length=128)


class ItemFeedbackRequest(BaseModel):
    version_id: int | None = None
    section: VotableSectionKey
    item_key: str | None = None
    item_index: int | None = Field(default=None, ge=0)
    vote: ItemVote | None = None

    @model_validator(mode="after")
    def require_item_identifier(self) -> ItemFeedbackRequest:
        if not (self.item_key or "").strip() and self.item_index is None:
            raise ValueError("Укажите item_key или item_index")
        return self
