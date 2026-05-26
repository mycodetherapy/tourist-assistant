"""Тесты слоя SQLite без вызова LLM."""

from __future__ import annotations

import os
import tempfile
import unittest

from db.connection import init_db
from db.repository import (
    create_trip,
    get_latest_itinerary,
    get_preferences,
    get_user_profile,
    has_user_profile,
    list_planned_trips,
    save_itinerary_version,
    save_preferences,
    save_user_profile,
)


class TestRepository(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        os.environ["DATABASE_PATH"] = os.path.join(self._tmpdir.name, "test.db")
        init_db()

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_trip_preferences_and_version(self) -> None:
        trip_id = create_trip("Москва", "1-3 июля 2026", "Казань", "тест")
        prefs = {"pace": "moderate", "budget": "medium", "interests": ["музеи"]}
        save_preferences(trip_id, prefs)
        loaded = get_preferences(trip_id)
        self.assertEqual(loaded["pace"], "moderate")

        program = {
            "tickets": "✈️",
            "events": "музей",
            "dining": "кафе",
            "transport": "метро",
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

    def test_list_planned_trips(self) -> None:
        self.assertEqual(list_planned_trips(), [])
        trip_id = create_trip("Сочи", "август 2026", "Москва", "отдых")
        self.assertEqual(list_planned_trips(), [])
        save_itinerary_version(
            trip_id,
            {
                "tickets": "t",
                "events": "e",
                "dining": "d",
                "transport": "tr",
                "lifehacks": "l",
            },
        )
        planned = list_planned_trips()
        self.assertEqual(len(planned), 1)
        self.assertEqual(planned[0].id, trip_id)
        self.assertEqual(planned[0].last_version, 1)

    def test_profile_fallback_from_trip(self) -> None:
        """Если user_profile пуст, берём prefs последней поездки."""
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
