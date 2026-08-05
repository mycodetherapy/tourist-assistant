"""Тесты лайкнутых маршрутов при partial rebuild."""

from __future__ import annotations

import json
import os
import unittest

from langchain_core.messages import ToolMessage

from db import (
    create_trip,
    get_latest_itinerary,
    save_itinerary_version,
    save_section_artifact,
    upsert_item_feedback,
)
from models.routes import GeoPoint, PoiPoint, RouteMaterials, RouteProgram, RouteStop, TripRouteCase
from program.item_key import make_item_key
from program.parse_items import parse_program_sections
from program.route_feedback import (
    MAX_LIKED_ROUTES_PER_TRIP,
    build_route_feedback_context,
    count_liked_routes,
    extract_liked_routes,
    merge_preserved_with_new_routes,
    snapshot_route_feedback,
)
from search.route_materials_store import ROUTE_MATERIALS_SECTION
from services.trip_service import TripService
from tests.db_test_helpers import skip_unless_pg, truncate_pg_tables
from tests.test_item_feedback import _sample_routes_program


def _route_materials() -> RouteMaterials:
    base = [
        ("l1", "museums", "Национальный музей", 45.20, 54.20),
        ("l2", "landmarks", "Площадь", 45.21, 54.21),
        ("l3", "parks", "Парк Победы", 45.22, 54.22),
        ("l4", "landmarks", "Музей искусств", 45.23, 54.23),
        ("l5", "embankments", "Набережная", 45.24, 54.24),
        ("l6", "monuments", "Памятник", 45.25, 54.25),
        ("l7", "theaters", "Театр", 45.26, 54.26),
        ("l8", "landmarks", "Собор", 45.27, 54.27),
    ]
    return RouteMaterials(
        city="Казань",
        dates="июль",
        provider="fallback",
        leisure_points=[
            PoiPoint(
                poi_id=pid,
                tag=tag,
                name=name,
                coordinates=GeoPoint(lon=lon, lat=lat),
                maps_url=f"https://example.com/{pid}",
            )
            for pid, tag, name, lon, lat in base
        ],
        dining_options=[],
    )


def _tool_messages(materials: RouteMaterials) -> list[ToolMessage]:
    payload = {
        "materials": materials.model_dump(),
        "materials_digest": ", ".join(p.name for p in materials.leisure_points[:5]),
        "leisure_count": len(materials.leisure_points),
    }
    return [
        ToolMessage(
            content=json.dumps(payload, ensure_ascii=False),
            tool_call_id="m",
            name="search_route_materials",
        )
    ]


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


@skip_unless_pg
class TestRouteFeedback(unittest.TestCase):
    def setUp(self) -> None:
        truncate_pg_tables()
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

    def test_extract_liked_from_preserved_flag_without_vote(self) -> None:
        program = dict(self.program)
        routes = RouteProgram.model_validate(program["routes"])
        cases = [
            routes.cases[0].model_copy(update={"preserved": True}),
            *routes.cases[1:],
        ]
        program["routes"] = RouteProgram(cases=cases).model_dump()
        liked = extract_liked_routes(program, self.trip_id)
        self.assertEqual(len(liked), 1)
        self.assertEqual(liked[0].case_id, "A")

    def test_double_partial_rebuild_keeps_liked_routes(self) -> None:
        from agents.finalize_helpers import resolve_routes_program
        from agents.route_postprocess import format_routes_text

        materials = _route_materials()
        save_section_artifact(
            self.trip_id,
            ROUTE_MATERIALS_SECTION,
            {"schema_version": 1, "materials": materials.model_dump()},
            digest="Казань POI",
        )
        self._like_route_index(0)
        messages = _tool_messages(materials)

        snap = snapshot_route_feedback(self.program, self.trip_id, "routes")
        assert snap is not None
        routes1, routes_text1 = resolve_routes_program(
            messages,
            None,
            base_program=self.program,
            trip_id=self.trip_id,
            expected_city="Казань",
            rebuild_scope="routes",
            route_feedback_snapshot=snap,
        )
        prog1 = {
            **self.program,
            "routes": routes1.model_dump(),
            "routes_text": routes_text1,
        }
        save_itinerary_version(self.trip_id, prog1, scope="routes")

        base2 = get_latest_itinerary(self.trip_id)["program"]
        self.assertTrue(any(c.get("preserved") for c in base2["routes"]["cases"]))
        snap2 = snapshot_route_feedback(base2, self.trip_id, "routes")
        assert snap2 is not None
        self.assertGreaterEqual(len(snap2["liked_cases"]), 1)

        routes2, _ = resolve_routes_program(
            messages,
            None,
            base_program=base2,
            trip_id=self.trip_id,
            expected_city="Казань",
            rebuild_scope="routes",
            route_feedback_snapshot=snap2,
        )
        case_ids = [c.case_id for c in routes2.cases]
        self.assertIn("A", case_ids)
        self.assertGreaterEqual(len(routes2.cases), 4)
        preserved_count = sum(1 for c in routes2.cases if c.preserved)
        self.assertGreaterEqual(preserved_count, 1)


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
