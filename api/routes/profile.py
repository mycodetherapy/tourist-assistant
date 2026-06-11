"""Профиль пользователя и BYOK-настройки."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response

from api.auth.service import (
    AuthError,
    get_llm_settings_view,
    remove_llm_key,
    save_llm_settings,
)
from api.deps import get_current_user, get_trip_service
from api.schemas.requests import UpdateSettingsRequest
from api.schemas.responses import ProfileResponse, SettingsResponse
from db.users import User
from onboarding.preferences import TripPreferences
from services.trip_service import TripService

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_model=ProfileResponse)
def get_profile(
    user: User = Depends(get_current_user),
    service: TripService = Depends(get_trip_service),
) -> ProfileResponse:
    data = service.get_profile(user.id)
    prefs = TripPreferences.model_validate(data) if data else None
    return ProfileResponse(preferences=prefs)


@router.get("/settings", response_model=SettingsResponse)
def get_settings(user: User = Depends(get_current_user)) -> SettingsResponse:
    data = get_llm_settings_view(user.id)
    return SettingsResponse.model_validate(data)


@router.put("/settings", response_model=SettingsResponse)
def update_settings(
    body: UpdateSettingsRequest,
    user: User = Depends(get_current_user),
) -> SettingsResponse:
    try:
        save_llm_settings(
            user.id,
            llm_api_key=body.llm_api_key,
            llm_base_url=body.llm_base_url,
            llm_model=body.llm_model,
        )
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    data = get_llm_settings_view(user.id)
    return SettingsResponse.model_validate(data)


@router.delete("/settings/llm-key", status_code=204, response_class=Response)
def delete_llm_key(user: User = Depends(get_current_user)) -> Response:
    remove_llm_key(user.id)
    return Response(status_code=204)
