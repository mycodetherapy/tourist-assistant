"""Голоса api-node (routes_text ##) должны читаться worker'ом."""

from __future__ import annotations

import unittest

from db import create_trip, save_itinerary_version, upsert_item_feedback
from program.item_key import make_item_key
from program.parse_items import _parse_routes_from_text
from program.route_feedback import extract_liked_routes
from tests.db_test_helpers import skip_unless_pg, truncate_pg_tables
from tests.test_route_feedback import _sample_program


@skip_unless_pg
class TestLegacyRouteVoteKeys(unittest.TestCase):
    def test_likes_via_routes_text_key_are_visible_to_worker(self) -> None:
        truncate_pg_tables()
        trip_id = create_trip("Казань", "июль", "Москва", "тест")
        program = _sample_program()
        version_id = save_itinerary_version(trip_id, program)

        text_items = _parse_routes_from_text(program["routes_text"]).items
        self.assertGreaterEqual(len(text_items), 1)
        legacy_key = make_item_key("routes", text_items[0])
        upsert_item_feedback(trip_id, version_id, "routes", 0, legacy_key, 1)

        liked = extract_liked_routes(program, trip_id)
        self.assertEqual(len(liked), 1)
        self.assertEqual(liked[0].case_id, "A")


if __name__ == "__main__":
    unittest.main()
