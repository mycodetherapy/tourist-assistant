"""Ответы REST API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from models.schemas import FinalProgram

ProgramSectionKey = Literal["routes", "lifehacks"]
ItemVote = Literal[1, -1]
from onboarding.preferences import TripPreferences

RunStatusName = Literal["queued", "running", "completed", "failed"]


class TripSummaryResponse(BaseModel):
    id: int
    city: str
    updated_at: str


class TripDetailResponse(BaseModel):
    id: int
    city: str
    user_query: str | None
    created_at: str
    updated_at: str


class CreateTripResponse(BaseModel):
    trip_id: int
    run_id: str | None = None


class ProgramItemResponse(BaseModel):
    index: int
    item_key: str
    text: str
    vote: ItemVote | None = None
    poi_id: str | None = None


class ProgramSectionResponse(BaseModel):
    intro: str
    items: list[ProgramItemResponse] = Field(default_factory=list)


class StructuredProgramResponse(BaseModel):
    routes: ProgramSectionResponse
    route_stops: ProgramSectionResponse
    lifehacks: ProgramSectionResponse


class ProgramResponse(BaseModel):
    version: int
    version_id: int
    scope: str
    approved: bool
    program: FinalProgram
    sections: StructuredProgramResponse


class RunStatusResponse(BaseModel):
    run_id: str
    trip_id: int
    status: RunStatusName
    error: str | None = None
    version_id: int | None = None


class ProfileResponse(BaseModel):
    preferences: TripPreferences | None


class SettingsResponse(BaseModel):
    llm_key_configured: bool
    llm_key_preview: str | None = None
    llm_base_url: str
    llm_model: str


class GeocodeResultResponse(BaseModel):
    lat: float
    lon: float
    label: str


class GeocodeResponse(BaseModel):
    results: list[GeocodeResultResponse] = Field(default_factory=list)


class CityCenterResponse(BaseModel):
    lat: float
    lon: float
    label: str


class ReverseGeocodeResponse(BaseModel):
    lat: float
    lon: float
    label: str
