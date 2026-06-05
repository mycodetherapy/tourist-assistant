"""Профиль пользователя (дефолты опросника)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api.deps import get_trip_service
from api.schemas.responses import ProfileResponse
from onboarding.preferences import TripPreferences
from services.trip_service import TripService

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_model=ProfileResponse)
def get_profile(service: TripService = Depends(get_trip_service)) -> ProfileResponse:
    data = service.get_profile()
    prefs = TripPreferences.model_validate(data) if data else None
    return ProfileResponse(preferences=prefs)
