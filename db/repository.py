"""CRUD facade: PostgreSQL (DATABASE_URL обязателен)."""

from __future__ import annotations

from db.types import PlannedTripSummary, TripSummary

__all__ = [
    "PlannedTripSummary",
    "TripSummary",
    "create_trip",
    "delete_trip",
    "save_preferences",
    "get_preferences",
    "get_latest_trip_preferences",
    "has_user_profile",
    "get_user_profile",
    "ensure_user_profile_from_trips",
    "save_user_profile",
    "list_planned_trips",
    "list_trips",
    "get_trip",
    "trip_belongs_to_user",
    "next_version_number",
    "list_item_feedback_pairs",
    "prune_stale_item_feedback",
    "save_itinerary_version",
    "log_tool_run",
    "log_agent_run",
    "list_agent_runs",
    "list_tool_runs",
    "mark_latest_itinerary_approved",
    "list_trip_itinerary_programs",
    "get_latest_itinerary",
    "get_itinerary_version",
    "patch_itinerary_program",
    "list_item_feedback",
    "list_item_feedback_by_section",
    "list_item_feedback_by_index",
    "upsert_item_feedback",
    "delete_item_feedback",
    "delete_feedback_at_index",
    "save_section_artifact",
    "get_section_artifact",
]


def __getattr__(name: str):
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from db.backends import get_repository_backend

    return getattr(get_repository_backend(), name)
