"""Тесты search_context из предпочтений."""

from __future__ import annotations

import unittest

from onboarding.preferences import TripPreferences, build_search_context
from search.context import clear_search_context, enrich_query, set_session


class TestPreferences(unittest.TestCase):
    def test_build_search_context(self) -> None:
        prefs = TripPreferences(
            pace="relaxed",
            budget="economy",
            interests=["музеи", "театр"],
            cuisine="итальянская",
            min_restaurant_rating=4.7,
            transport_preference="metro",
            travel_party="couple",
            special_notes="без очередей",
        )
        ctx = build_search_context(prefs)
        self.assertIn("музеи", ctx)
        self.assertIn("4.7", ctx)

    def test_enrich_query(self) -> None:
        clear_search_context()
        prefs = TripPreferences(
            pace="moderate",
            budget="medium",
            transport_preference="mixed",
            travel_party="solo",
        )
        set_session(prefs, build_search_context(prefs))
        enriched = enrich_query("афиша Москва")
        self.assertIn("афиша Москва", enriched)
        self.assertGreater(len(enriched), len("афиша Москва"))
        clear_search_context()


if __name__ == "__main__":
    unittest.main()
