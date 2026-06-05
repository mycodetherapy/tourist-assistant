"""Тела запросов REST API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from onboarding.preferences import TripPreferences

RebuildScope = Literal["full", "tickets", "events", "dining", "lifehacks"]
ReviewAction = Literal["approve", "save_draft", "rebuild"]


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
