"""Зависимости FastAPI."""

from __future__ import annotations

from services.run_manager import RunManager
from services.trip_service import TripService

_trip_service = TripService()
_run_manager = RunManager(_trip_service)


def get_trip_service() -> TripService:
    return _trip_service


def get_run_manager() -> RunManager:
    return _run_manager
