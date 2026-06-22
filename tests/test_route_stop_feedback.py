"""Тесты голосования за отдельные остановки маршрута."""

from __future__ import annotations

import os
import unittest

from db.sqlite import repository as db_sqlite
from models.routes import GeoPoint, PoiPoint
from program.feedback_prune import find_stale_feedback_keys
from program.item_key import make_route_stop_key
from program.route_feedback import (
    expand_similar_banned_poi,
    load_poi_stop_vote_sets,
    rebuild_poi_preferences,
)
from program.route_stops import collect_route_stop_poi_ids
from services.trip_service import TripService
from tests.db_test_helpers import use_sqlite_db
from tests.test_item_feedback import _sample_routes_program


class TestRouteStopFeedback(unittest.TestCase):
    def setUp(self) -> None:
        self._db_path = "/tmp/test_route_stop_feedback.db"
        self._backend = use_sqlite_db(self._db_path)
        self._backend.__enter__()
        self.trip_id = db_sqlite.create_trip("Казань", "июль", "Москва", "тест")
        self.program = _sample_routes_program(["A", "B", "C"])
        db_sqlite.save_itinerary_version(self.trip_id, self.program, scope="full")
        self.service = TripService()

    def tearDown(self) -> None:
        self._backend.__exit__(None, None, None)

    def test_vote_stop_like_and_unlike(self) -> None:
        pois = collect_route_stop_poi_ids(self.program)
        poi_id = next(iter(pois))
        key = make_route_stop_key(poi_id)
        self.service.set_item_feedback(
            self.trip_id,
            section="route_stops",
            item_key=key,
            vote=1,
        )
        liked, disliked = load_poi_stop_vote_sets(self.trip_id)
        self.assertIn(poi_id, liked)
        view = self.service.get_program_view(self.trip_id)
        assert view is not None
        stop_item = next(i for i in view.sections["route_stops"].items if i.poi_id == poi_id)
        self.assertEqual(stop_item.vote, 1)

        self.service.set_item_feedback(
            self.trip_id,
            section="route_stops",
            item_key=key,
            vote=None,
        )
        liked, _ = load_poi_stop_vote_sets(self.trip_id)
        self.assertNotIn(poi_id, liked)

    def test_disliked_stop_in_banned(self) -> None:
        pois = collect_route_stop_poi_ids(self.program)
        poi_id = next(iter(pois))
        self.service.set_item_feedback(
            self.trip_id,
            section="route_stops",
            item_key=make_route_stop_key(poi_id),
            vote=-1,
        )
        preferred, banned, _ = rebuild_poi_preferences(self.trip_id, None, [])
        self.assertIn(poi_id, banned)
        self.assertNotIn(poi_id, preferred)

    def test_route_stops_dislikes_persist_after_routes_rebuild(self) -> None:
        pois = collect_route_stop_poi_ids(self.program)
        poi_id = next(iter(pois))
        self.service.set_item_feedback(
            self.trip_id,
            section="route_stops",
            item_key=make_route_stop_key(poi_id),
            vote=-1,
        )
        _, disliked = load_poi_stop_vote_sets(self.trip_id)
        self.assertIn(poi_id, disliked)

        new_program = _sample_routes_program(["N-A", "N-B", "N-C"])
        db_sqlite.save_itinerary_version(self.trip_id, new_program, scope="routes")

        _, disliked = load_poi_stop_vote_sets(self.trip_id)
        self.assertIn(poi_id, disliked)
        self.assertEqual(
            db_sqlite.list_item_feedback_by_section(self.trip_id, "route_stops"),
            {make_route_stop_key(poi_id): -1},
        )

    def test_expand_similar_banned_poi_same_tag(self) -> None:
        leisure = [
            PoiPoint(
                poi_id="a",
                tag="museums",
                name="Музей деревянного зодчества",
                coordinates=GeoPoint(lon=40.0, lat=57.0),
                maps_url="https://example.com/a",
            ),
            PoiPoint(
                poi_id="b",
                tag="museums",
                name="Музей деревянного зодчества (филиал)",
                coordinates=GeoPoint(lon=40.1, lat=57.1),
                maps_url="https://example.com/b",
            ),
            PoiPoint(
                poi_id="c",
                tag="landmarks",
                name="Собор",
                coordinates=GeoPoint(lon=40.2, lat=57.2),
                maps_url="https://example.com/c",
            ),
        ]
        banned = expand_similar_banned_poi(leisure, {"a"})
        self.assertIn("a", banned)
        self.assertIn("b", banned)
        self.assertNotIn("c", banned)

    def test_expand_similar_bans_ushakov_monument_with_cathedral(self) -> None:
        leisure = [
            PoiPoint(
                poi_id="cathedral",
                tag="temples",
                name="Собор Святого Феодора Ушакова",
                coordinates=GeoPoint(lon=45.0, lat=54.0),
                maps_url="https://example.com/cathedral",
            ),
            PoiPoint(
                poi_id="monument",
                tag="monuments",
                name="Памятник Ушакову (Саранск)",
                coordinates=GeoPoint(lon=45.1, lat=54.1),
                maps_url="https://example.com/monument",
            ),
            PoiPoint(
                poi_id="park",
                tag="parks",
                name="Парк культуры",
                coordinates=GeoPoint(lon=45.2, lat=54.2),
                maps_url="https://example.com/park",
            ),
        ]
        banned = expand_similar_banned_poi(leisure, {"cathedral"})
        self.assertIn("cathedral", banned)
        self.assertIn("monument", banned)
        self.assertNotIn("park", banned)

    def test_stale_route_stops_on_reset_clears_likes_keeps_dislikes(self) -> None:
        pois = collect_route_stop_poi_ids(self.program)
        poi_id = next(iter(pois))
        key = make_route_stop_key(poi_id)
        self.service.set_item_feedback(
            self.trip_id,
            section="route_stops",
            item_key=key,
            vote=-1,
        )
        stale = find_stale_feedback_keys(
            self.program,
            "routes",
            existing=[("route_stops", key)],
            reset_route_stops=True,
            route_stop_votes={key: -1},
        )
        self.assertEqual(stale, [])

    def test_get_program_view_keeps_stop_votes(self) -> None:
        pois = collect_route_stop_poi_ids(self.program)
        poi_id = next(iter(pois))
        self.service.set_item_feedback(
            self.trip_id,
            section="route_stops",
            item_key=make_route_stop_key(poi_id),
            vote=1,
        )
        self.service.get_program_view(self.trip_id)
        liked, _ = load_poi_stop_vote_sets(self.trip_id)
        self.assertIn(poi_id, liked)


if __name__ == "__main__":
    unittest.main()
