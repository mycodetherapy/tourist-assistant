"""Изоляция SQLite в unit-тестах при DATABASE_URL в .env."""

from __future__ import annotations

import os
from contextlib import ExitStack
from unittest.mock import patch

from db.connection import init_db
from db.sqlite import repository as sqlite_repo

_TRIP_SERVICE_DB_NAMES = (
    "create_trip",
    "delete_item_feedback",
    "delete_trip",
    "get_itinerary_version",
    "get_latest_itinerary",
    "get_preferences",
    "get_trip",
    "get_user_profile",
    "list_item_feedback",
    "list_item_feedback_by_index",
    "list_trips",
    "log_agent_run",
    "save_itinerary_version",
    "save_preferences",
    "save_user_profile",
    "upsert_item_feedback",
)


def use_sqlite_db(db_path: str) -> ExitStack:
    """Контекст: repository facade и TripService работают через SQLite."""
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["DATABASE_PATH"] = db_path
    os.environ.pop("DATABASE_URL", None)
    init_db()

    stack = ExitStack()
    stack.enter_context(
        patch("db.backends.get_repository_backend", return_value=sqlite_repo)
    )
    import services.trip_service as trip_service_mod
    import program.route_feedback as route_feedback_mod

    for name in _TRIP_SERVICE_DB_NAMES:
        stack.enter_context(
            patch.object(trip_service_mod, name, getattr(sqlite_repo, name))
        )
    stack.enter_context(
        patch.object(
            route_feedback_mod,
            "list_item_feedback",
            sqlite_repo.list_item_feedback,
        )
    )
    return stack
