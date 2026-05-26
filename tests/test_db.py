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
    save_itinerary_version,
    save_preferences,
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


if __name__ == "__main__":
    unittest.main()
