"""SQLite-хранилище поездок и версий программы."""

from db.connection import get_database_path, init_db
from db.repository import (
    TripSummary,
    create_trip,
    get_latest_itinerary,
    get_preferences,
    get_trip,
    list_trips,
    save_itinerary_version,
    save_preferences,
    update_trip_status,
)

__all__ = [
    "TripSummary",
    "create_trip",
    "get_database_path",
    "get_latest_itinerary",
    "get_preferences",
    "get_trip",
    "init_db",
    "list_trips",
    "save_itinerary_version",
    "save_preferences",
    "update_trip_status",
]
