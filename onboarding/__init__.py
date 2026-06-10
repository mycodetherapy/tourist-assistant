"""Опросник и модель предпочтений пользователя."""

from onboarding.preferences import (
    TripPreferences,
    build_search_context,
    normalize_trip_preferences,
)
from onboarding.questionnaire import (
    resolve_preferences_for_new_trip,
    run_clarifying_questionnaire,
    run_questionnaire,
)

__all__ = [
    "TripPreferences",
    "build_search_context",
    "normalize_trip_preferences",
    "resolve_preferences_for_new_trip",
    "run_clarifying_questionnaire",
    "run_questionnaire",
]
