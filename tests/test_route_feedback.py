"""Тесты лайкнутых маршрутов при partial rebuild."""

from __future__ import annotations

import os
import unittest

from db import (
    create_trip,
    init_db,
    save_itinerary_version,
    upsert_item_feedback,
)
from models.routes import GeoPoint, PoiPoint, RouteProgram, RouteStop, TripRouteCase
from program.item_key import make_item_key
from program.parse_items import parse_program_sections
from program.route_feedback import (
    MAX_LIKED_ROUTES_PER_TRIP,
    build_route_feedback_context,
    count_liked_routes,
    extract_liked_routes,
    merge_preserved_with_new_routes,
)
from services.trip_service import TripService


def _sample_program() -> dict:
    cases = [
        TripRouteCase(
            case_id="A",
            title="Компактный",
            summary="3 остановки",
            stops=[
                RouteStop(order=1, kind="leisure", poi_id="l1", narrative="Музей"),
                RouteStop(order=2, kind="leisure", poi_id="l2", narrative="Площадь"),
            ],
            maps_route_url="https://yandex.ru/maps/?rtext=1",
        ),
        TripRouteCase(
            case_id="B",
            title="Средний",
            summary="4 остановки",
            stops=[
                RouteStop(order=1, kind="leisure", poi_id="l3", narrative="Парк"),
            ],
            maps_route_url="https://yandex.ru/maps/?rtext=2",
        ),
        TripRouteCase(
            case_id="C",
            title="Длинный",
            summary="5 остановок",
            stops=[
                RouteStop(order=1, kind="leisure", poi_id="l4", narrative="Набережная"),
            ],
            maps_route_url="https://yandex.ru/maps/?rtext=3",
        ),
    ]
    program = RouteProgram(cases=cases)
    from agents.route_postprocess import format_routes_text

    return {
        "tickets": "- Aviasales",
        "routes": program.model_dump(),
        "routes_text": format_routes_text(program),
        "lifehacks": "- Совет",
    }


class TestRouteFeedback(unittest.TestCase):
    def setUp(self) -> None:
        self._db_path = "/tmp/test_route_feedback.db"
        os.environ["DATABASE_PATH"] = self._db_path
        if os.path.exists(self._db_path):
            os.remove(self._db_path)
        init_db()
        self.trip_id = create_trip("Казань", "июль", "Москва", "тест")
        self.program = _sample_program()
        self.version_id = save_itinerary_version(self.trip_id, self.program)
        self.service = TripService()

    def _like_route_index(self, index: int) -> None:
        parsed = parse_program_sections(self.program)
        key = make_item_key("routes", parsed.routes.items[index])
        upsert_item_feedback(
            self.trip_id, self.version_id, "routes", index, key, 1
        )

    def test_extract_liked_routes(self) -> None:
        self._like_route_index(0)
        self._like_route_index(1)
        liked = extract_liked_routes(self.program, self.trip_id)
        self.assertEqual(len(liked), 2)
        self.assertEqual(liked[0].case_id, "A")
        self.assertTrue(liked[0].preserved)
        self.assertEqual(liked[1].case_id, "B")

    def test_disliked_not_in_liked(self) -> None:
        parsed = parse_program_sections(self.program)
        key = make_item_key("routes", parsed.routes.items[2])
        upsert_item_feedback(
            self.trip_id, self.version_id, "routes", 2, key, -1
        )
        liked = extract_liked_routes(self.program, self.trip_id)
        self.assertEqual(liked, [])

    def test_merge_preserved_with_new(self) -> None:
        self._like_route_index(0)
        preserved = extract_liked_routes(self.program, self.trip_id)
        new = RouteProgram(
            cases=[
                TripRouteCase(case_id="A", title="n1", summary="s", stops=[]),
                TripRouteCase(case_id="B", title="n2", summary="s", stops=[]),
                TripRouteCase(case_id="C", title="n3", summary="s", stops=[]),
            ]
        )
        merged = merge_preserved_with_new_routes(preserved, new)
        self.assertEqual(len(merged.cases), 4)
        self.assertEqual(merged.cases[0].case_id, "A")
        self.assertTrue(merged.cases[0].preserved)
        self.assertEqual(merged.cases[1].case_id, "N-A")
        self.assertFalse(merged.cases[1].preserved)

    def test_feedback_prompt_includes_stops_and_themes(self) -> None:
        self._like_route_index(0)
        ctx = build_route_feedback_context(
            self.program, self.trip_id, rebuild_scope="routes"
        )
        assert ctx is not None
        self.assertIn("Музей", ctx.llm_instructions)
        self.assertIn("Площадь", ctx.llm_instructions)
        self.assertIn("мотив", ctx.llm_instructions.lower())
        self.assertIn("Запрещённые poi_id", ctx.llm_instructions)
        self.assertIn("l1", ctx.llm_instructions)
        self.assertIn("вдохновения", ctx.llm_instructions)

    def test_full_rebuild_soft_route_like_hints(self) -> None:
        self._like_route_index(1)
        ctx = build_route_feedback_context(
            self.program, self.trip_id, rebuild_scope="full"
        )
        assert ctx is not None
        self.assertIn("Параметры лайкнутых маршрутов", ctx.llm_instructions)
        self.assertIn("средний", ctx.llm_instructions.lower())
        self.assertNotIn("останутся без изменений", ctx.llm_instructions)
        self.assertNotIn("Запрещённые poi_id", ctx.llm_instructions)

    def test_church_theme_hint_from_stop_names(self) -> None:
        from program.route_feedback import _infer_soft_themes

        themes = _infer_soft_themes(
            ["Казанский собор", "Спас на Крови", "Исаакиевский собор"],
            set(),
        )
        self.assertIn("культовая архитектура", themes)

    def test_unlike_removes_from_liked_extract(self) -> None:
        self._like_route_index(0)
        self.assertEqual(len(extract_liked_routes(self.program, self.trip_id)), 1)
        parsed = parse_program_sections(self.program)
        key = make_item_key("routes", parsed.routes.items[0])
        self.service.set_item_feedback(
            self.trip_id,
            section="routes",
            item_key=key,
            vote=None,
        )
        self.assertEqual(extract_liked_routes(self.program, self.trip_id), [])

    def test_like_limit_enforced(self) -> None:
        from unittest.mock import patch

        self._like_route_index(0)
        self._like_route_index(1)
        with patch("program.route_feedback.MAX_LIKED_ROUTES_PER_TRIP", 2):
            with self.assertRaises(ValueError):
                self.service.set_item_feedback(
                    self.trip_id,
                    section="routes",
                    item_index=2,
                    vote=1,
                )


class TestSectionQualityPreserved(unittest.TestCase):
    def test_routes_with_preserved_and_new(self) -> None:
        from agents.section_quality import _routes_issues

        preserved = TripRouteCase(
            case_id="A",
            title="Liked",
            summary="s",
            preserved=True,
            maps_route_url="https://maps",
            stops=[
                RouteStop(order=1, kind="leisure", poi_id="p1", narrative="x"),
                RouteStop(order=2, kind="leisure", poi_id="p2", narrative="y"),
                RouteStop(order=3, kind="leisure", poi_id="p3", narrative="z"),
            ],
        )
        new_cases = []
        for cid, pids in (
            ("N-A", ("n1", "n2", "n3")),
            ("N-B", ("n4", "n5", "n6", "n7")),
            ("N-C", ("n8", "n9", "n10", "n11", "n12")),
        ):
            new_cases.append(
                TripRouteCase(
                    case_id=cid,
                    title=cid,
                    summary="s",
                    maps_route_url="https://maps",
                    stops=[
                        RouteStop(order=i + 1, kind="leisure", poi_id=pid, narrative="x")
                        for i, pid in enumerate(pids)
                    ],
                )
            )
        program = {
            "routes": RouteProgram(cases=[preserved, *new_cases]).model_dump(),
            "routes_text": "x" * 100,
        }
        issues = _routes_issues(program)
        self.assertEqual(issues, [])


if __name__ == "__main__":
    unittest.main()
