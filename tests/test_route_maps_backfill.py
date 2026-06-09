"""Тесты восстановления maps_route_url при пересборке маршрутов."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agents.finalize_helpers import resolve_routes_program
from agents.route_postprocess import build_fallback_route_program
from db.connection import init_db
from db.repository import create_trip
from models.routes import GeoPoint, PoiPoint, RouteMaterials, RouteProgram, RouteStop, TripRouteCase
from search.route_materials_store import (
    backfill_route_materials_from_program,
    load_route_materials_for_trip,
)
from search.yandex.route_url import build_maps_route_url, parse_maps_route_points


def _sample_materials() -> RouteMaterials:
    points = [
        PoiPoint(
            poi_id=f"p{i}",
            tag="landmarks",
            name=f"Место {i}",
            coordinates=GeoPoint(lon=50.1 + i * 0.01, lat=53.2 + i * 0.005),
            maps_url=f"https://example.com/{i}",
        )
        for i in range(8)
    ]
    return RouteMaterials(city="Самара", dates="июнь", leisure_points=points)


def _program_with_maps() -> dict:
    materials = _sample_materials()
    program = build_fallback_route_program(materials)
    return {
        "tickets": "ok",
        "routes": program.model_dump(),
        "routes_text": "routes",
        "lifehacks": "tip",
    }


class TestRouteMapsBackfill(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmpdir.name) / "test.db"
        self._env_patch = patch.dict(
            "os.environ", {"DATABASE_PATH": str(self._db_path)}, clear=False
        )
        self._env_patch.start()
        init_db()

    def tearDown(self) -> None:
        self._env_patch.stop()
        self._tmpdir.cleanup()

    def test_parse_maps_route_points(self) -> None:
        url = build_maps_route_url(
            [
                GeoPoint(lon=50.1, lat=53.2),
                GeoPoint(lon=50.2, lat=53.3),
            ]
        )
        points = parse_maps_route_points(url)
        self.assertEqual(len(points), 2)
        self.assertAlmostEqual(points[0].lat, 53.2)
        self.assertAlmostEqual(points[1].lon, 50.2)

    def test_backfill_from_saved_program(self) -> None:
        trip_id = create_trip("Самара", "июнь", "Москва", "тест")
        base = _program_with_maps()
        self.assertTrue(
            backfill_route_materials_from_program(
                trip_id, base, city="Самара", dates="июнь"
            )
        )
        cached = load_route_materials_for_trip(trip_id)
        self.assertIsNotNone(cached)
        assert cached is not None
        self.assertGreaterEqual(len(cached.leisure_points), 3)

    def test_resolve_rebuilds_maps_without_db_cache(self) -> None:
        trip_id = create_trip("Самара", "июнь", "Москва", "тест")
        base = _program_with_maps()
        draft = RouteProgram(
            cases=[
                TripRouteCase(
                    case_id=cid,
                    title=cid,
                    summary="",
                    stops=[
                        RouteStop(
                            order=1,
                            kind="leisure",
                            poi_id="p0",
                            narrative="Место 0",
                        ),
                        RouteStop(
                            order=2,
                            kind="leisure",
                            poi_id="p1",
                            narrative="Место 1",
                        ),
                        RouteStop(
                            order=3,
                            kind="leisure",
                            poi_id="p2",
                            narrative="Место 2",
                        ),
                    ],
                )
                for cid in ("A", "B", "C")
            ]
        )
        program, _ = resolve_routes_program(
            [],
            draft.model_dump(),
            base_program=base,
            expected_city="Самара",
            trip_id=trip_id,
            dates="июнь",
        )
        for case in program.cases:
            self.assertTrue(
                case.maps_route_url.startswith("https://yandex.ru/maps/"),
                case.case_id,
            )

    def test_repair_from_history_when_latest_has_no_maps(self) -> None:
        from agents.finalize_helpers import repair_program_routes
        from db.repository import save_itinerary_version

        trip_id = create_trip("Йошкар-Ола", "июнь", "Москва", "тест")
        good = _program_with_maps()
        save_itinerary_version(trip_id, good, scope="full")
        broken = dict(good)
        broken_routes = dict(good["routes"])
        broken_cases = []
        for case in good["routes"]["cases"]:
            broken_case = dict(case)
            broken_case["maps_route_url"] = ""
            broken_cases.append(broken_case)
        broken_routes["cases"] = broken_cases
        broken["routes"] = broken_routes
        save_itinerary_version(trip_id, broken, scope="routes")

        repaired = repair_program_routes(
            broken,
            trip_id=trip_id,
            city="Йошкар-Ола",
            dates="июнь",
        )
        cases = repaired["routes"]["cases"]
        for case in cases:
            self.assertTrue(str(case.get("maps_route_url", "")).startswith("https://"))


if __name__ == "__main__":
    unittest.main()
