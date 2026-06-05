"""Ответы REST API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from models.schemas import FinalProgram
from onboarding.preferences import TripPreferences

RunStatusName = Literal["queued", "running", "completed", "failed"]


class TripSummaryResponse(BaseModel):
    id: int
    city: str
    dates: str
    origin_city: str
    status: str
    updated_at: str


class TripDetailResponse(BaseModel):
    id: int
    city: str
    dates: str
    origin_city: str
    user_query: str | None
    status: str
    created_at: str
    updated_at: str


class CreateTripResponse(BaseModel):
    trip_id: int
    run_id: str | None = None


class ProgramResponse(BaseModel):
    version: int
    scope: str
    approved: bool
    program: FinalProgram


class RunStatusResponse(BaseModel):
    run_id: str
    trip_id: int
    status: RunStatusName
    error: str | None = None
    version_id: int | None = None


class ReviewResponse(BaseModel):
    trip_id: int
    status: str
    run_id: str | None = None


class ProfileResponse(BaseModel):
    preferences: TripPreferences | None
