"""Shared repository DTOs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TripSummary:
    id: int
    city: str
    dates: str
    origin_city: str
    updated_at: str


@dataclass(frozen=True)
class PlannedTripSummary:
    id: int
    city: str
    dates: str
    origin_city: str
    updated_at: str
    last_version: int
    last_scope: str
