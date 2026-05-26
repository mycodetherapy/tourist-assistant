"""SQLite-хранилище поездок и версий программы."""

from db.connection import get_database_path, init_db
from db.repository import (
    PlannedTripSummary,
    TripSummary,
    create_trip,
    ensure_user_profile_from_trips,
    get_latest_itinerary,
    get_preferences,
    get_trip,
    get_user_profile,
    has_user_profile,
    list_planned_trips,
    list_tool_runs,
    list_trips,
    log_tool_run,
    save_itinerary_version,
    save_preferences,
    save_user_profile,
    update_trip_status,
)

__all__ = [
    "PlannedTripSummary",
    "TripSummary",
    "create_trip",
    "ensure_user_profile_from_trips",
    "get_database_path",
    "get_latest_itinerary",
    "get_preferences",
    "get_trip",
    "get_user_profile",
    "has_user_profile",
    "init_db",
    "list_planned_trips",
    "list_tool_runs",
    "list_trips",
    "log_tool_run",
    "save_itinerary_version",
    "save_preferences",
    "save_user_profile",
    "update_trip_status",
]
