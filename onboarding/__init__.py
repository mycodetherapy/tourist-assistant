"""Опросник и модель предпочтений пользователя."""

from onboarding.preferences import (
    TripPreferences,
    build_search_context,
    merge_trip_preferences,
    normalize_trip_preferences,
)

__all__ = [
    "TripPreferences",
    "build_search_context",
    "merge_trip_preferences",
    "normalize_trip_preferences",
]
