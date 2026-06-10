"""Тесты search_context из предпочтений."""

from __future__ import annotations

import unittest

from onboarding.preferences import (
    TripPreferences,
    build_search_context,
    normalize_trip_preferences,
)
from search.context import clear_search_context, enrich_query, set_session


class TestPreferences(unittest.TestCase):
    def test_build_search_context(self) -> None:
        prefs = normalize_trip_preferences({"travel_party": "family"})
        ctx = build_search_context(prefs)
        self.assertIn("2 взрослых + 1 ребёнок", ctx)
        self.assertIn("насыщенный", ctx)
        self.assertNotIn("ресторан", ctx.lower())

    def test_normalize_strips_legacy_fields(self) -> None:
        prefs = normalize_trip_preferences(
            {
                "travel_party": "solo",
                "pace": "relaxed",
                "interests": ["театр"],
                "cuisine": "итальянская",
                "special_notes": "без очередей",
            }
        )
        self.assertEqual(prefs.travel_party, "solo")
        self.assertEqual(prefs.pace, "packed")
        self.assertEqual(prefs.transport_preference, "mixed")
        self.assertEqual(prefs.interests, [])
        self.assertEqual(prefs.special_notes, "")

    def test_enrich_query(self) -> None:
        clear_search_context()
        prefs = normalize_trip_preferences({"travel_party": "solo"})
        set_session(prefs, build_search_context(prefs))
        enriched = enrich_query("афиша Москва")
        self.assertIn("афиша Москва", enriched)
        self.assertGreater(len(enriched), len("афиша Москва"))
        clear_search_context()

    def test_null_rating_coerced(self) -> None:
        prefs = TripPreferences.model_validate(
            {
                "pace": "moderate",
                "budget": "medium",
                "min_restaurant_rating": None,
                "transport_preference": "mixed",
                "travel_party": "couple",
            }
        )
        self.assertEqual(prefs.min_restaurant_rating, 4.0)

    def test_legacy_profile_dict_gets_defaults(self) -> None:
        prefs = normalize_trip_preferences(
            {"pace": "packed", "budget": "medium", "interests": ["театр"]}
        )
        self.assertEqual(prefs.transport_preference, "mixed")
        self.assertEqual(prefs.travel_party, "couple")
        self.assertEqual(prefs.interests, [])


if __name__ == "__main__":
    unittest.main()
