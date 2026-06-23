"""PostgreSQL repository tests (mirror tests/test_db.py)."""

from __future__ import annotations

import unittest

from db.backends import get_repository_backend
from db.repository import (
    create_trip,
    delete_trip,
    get_latest_itinerary,
    get_preferences,
    get_trip,
    get_user_profile,
    has_user_profile,
    list_planned_trips,
    save_itinerary_version,
    save_preferences,
    save_user_profile,
)
from db.session import is_postgres_enabled
from tests.db_test_helpers import prepare_pg_env, skip_unless_test_pg, truncate_pg_tables


@skip_unless_test_pg
class TestPostgresRepository(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        prepare_pg_env()
        truncate_pg_tables()
        cls._backend = get_repository_backend().__name__

    def setUp(self) -> None:
        truncate_pg_tables()

    def test_backend_is_postgres(self) -> None:
        self.assertTrue(is_postgres_enabled())

    def test_trip_preferences_and_version(self) -> None:
        trip_id = create_trip("Москва", "1-3 июля 2026", "Казань", "тест")
        prefs = {"pace": "moderate", "budget": "medium", "interests": ["музеи"]}
        save_preferences(trip_id, prefs)
        loaded = get_preferences(trip_id)
        self.assertEqual(loaded["pace"], "moderate")

        program = {
            "tickets": "t",
            "events": "музей",
            "dining": "кафе",
            "lifehacks": "совет",
        }
        save_itinerary_version(trip_id, program, scope="full")
        latest = get_latest_itinerary(trip_id)
        self.assertIsNotNone(latest)
        assert latest is not None
        self.assertEqual(latest["version"], 1)
        self.assertEqual(latest["program"]["events"], "музей")

    def test_user_profile(self) -> None:
        self.assertFalse(has_user_profile())
        save_user_profile({"pace": "relaxed", "budget": "economy"})
        self.assertTrue(has_user_profile())
        profile = get_user_profile()
        self.assertIsNotNone(profile)
        assert profile is not None
        self.assertEqual(profile["pace"], "relaxed")

    def test_delete_trip_cascade(self) -> None:
        trip_id = create_trip("Казань", "июль 2026", "Москва", "тест")
        save_preferences(trip_id, {"pace": "moderate", "budget": "medium"})
        save_itinerary_version(
            trip_id,
            {"tickets": "t", "events": "e", "dining": "d", "lifehacks": "l"},
        )
        self.assertTrue(delete_trip(trip_id))
        self.assertIsNone(get_trip(trip_id))
        self.assertIsNone(get_preferences(trip_id))
        self.assertIsNone(get_latest_itinerary(trip_id))

    def test_list_planned_trips(self) -> None:
        self.assertEqual(list_planned_trips(), [])
        trip_id = create_trip("Сочи", "август 2026", "Москва", "отдых")
        save_itinerary_version(
            trip_id,
            {"tickets": "t", "events": "e", "dining": "d", "lifehacks": "l"},
        )
        planned = list_planned_trips()
        self.assertEqual(len(planned), 1)
        self.assertEqual(planned[0].id, trip_id)

    def test_profile_fallback_from_trip(self) -> None:
        trip_id = create_trip("Казань", "июль 2026", "Москва", "тест")
        save_preferences(
            trip_id,
            {"pace": "packed", "budget": "medium", "interests": ["театр"]},
        )
        self.assertTrue(has_user_profile())
        profile = get_user_profile()
        assert profile is not None
        self.assertEqual(profile["pace"], "packed")


if __name__ == "__main__":
    unittest.main()
