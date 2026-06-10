"""Тесты качества секций и critic."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from agents.critic import run_critic
from agents.section_quality import (
    critic_program_issues,
    is_garbage_section,
)
from langchain_core.messages import ToolMessage
from models.routes import (
    GeoPoint,
    PoiPoint,
    RouteMaterials,
    RouteProgram,
    RouteStop,
    TripRouteCase,
)
from agents.route_postprocess import build_fallback_route_program, finalize_route_program


def _sample_routes_program() -> dict:
    materials = RouteMaterials(
        city="Казань",
        dates="июль",
        provider="fallback",
        leisure_points=[
            PoiPoint(
                poi_id=f"l{i}",
                tag="landmarks",
                name=f"Место {i}",
                coordinates=GeoPoint(lon=49.1 + i * 0.008, lat=55.8 + (i % 2) * 0.004),
                maps_url=f"https://yandex.ru/maps/org/l{i}",
            )
            for i in range(8)
        ],
        dining_options=[],
    )
    program = build_fallback_route_program(materials)
    return program.model_dump()


class TestSectionQuality(unittest.TestCase):
    def test_garbage_events_detected(self) -> None:
        self.assertTrue(is_garbage_section(":[{", "events"))
        self.assertTrue(is_garbage_section(":[]", "events"))

    def test_valid_events_ok(self) -> None:
        text = (
            "Эрмитаж https://hermitagemuseum.org\n"
            "Русский музей https://rusmuseum.ru\n"
        )
        self.assertFalse(is_garbage_section(text, "events"))

    def test_critic_routes_requires_cached_poi(self) -> None:
        state = {
            "rebuild_scope": "routes",
            "trip_id": 99,
            "messages": [],
            "program": {
                "routes": _sample_routes_program(),
                "routes_text": "## Вариант A\nтест " * 20,
                "tickets": "ok",
                "lifehacks": "x",
            },
        }
        passed, notes = run_critic(state)
        self.assertFalse(passed)
        self.assertIn("сохранённого пула", notes)

    def test_critic_fails_garbage_routes_scope(self) -> None:
        state = {
            "rebuild_scope": "routes",
            "messages": [
                ToolMessage(content="{}", tool_call_id="1", name="search_route_materials"),
            ],
            "program": {
                "routes": {"cases": []},
                "routes_text": "",
                "tickets": "ok",
                "lifehacks": "x",
            },
        }
        passed, notes = run_critic(state)
        self.assertFalse(passed)
        self.assertIn("routes", notes)

    def test_critic_flags_identical_routes(self) -> None:
        dup = TripRouteCase(
            case_id="A",
            title="A",
            summary="s",
            stops=[
                RouteStop(order=1, kind="leisure", poi_id="l1", narrative="1"),
                RouteStop(order=2, kind="leisure", poi_id="l2", narrative="2"),
            ],
            maps_route_url="https://yandex.ru/maps/?same",
        )
        issues = critic_program_issues(
            {
                "routes": RouteProgram(
                    cases=[
                        dup,
                        dup.model_copy(update={"case_id": "B", "title": "B"}),
                        TripRouteCase(
                            case_id="C",
                            title="C",
                            summary="s",
                            stops=[
                                RouteStop(order=1, kind="leisure", poi_id="l7", narrative="7"),
                            ],
                            maps_route_url="https://yandex.ru/maps/?other",
                        ),
                    ]
                ).model_dump(),
                "routes_text": "## Вариант A\nтест " * 20,
            },
            "routes",
        )
        self.assertTrue(any("совпадают" in i or "похожи" in i for i in issues))
        self.assertTrue(any("maps_route_url" in i for i in issues))

    def test_critic_program_issues_routes_ok(self) -> None:
        routes = _sample_routes_program()
        issues = critic_program_issues(
            {
                "routes": routes,
                "routes_text": "## Вариант A\nтест " * 20,
                "lifehacks": "Совет один. Совет два. Совет три.",
            },
            "routes",
        )
        self.assertEqual(issues, [])

    def test_critic_tickets_international_only_plane(self) -> None:
        program = {
            "tickets": "Самолёт: рейс TK https://www.aviasales.ru/search/MOW0107IST0407",
        }
        issues = critic_program_issues(
            program,
            "tickets",
            origin_city="Москва",
            destination_city="Стамбул",
        )
        self.assertEqual(issues, [])

    def test_critic_tickets_long_route_no_bus(self) -> None:
        program = {
            "tickets": (
                "**Самолёт**: SU https://www.aviasales.ru/search/MOW1008KZN1208 "
                "**Поезд**: РЖД https://www.tutu.ru/poezda/Moskva/Kazan/?date=10.08.2026 "
                + "x" * 40
            ),
        }
        with patch(
            "search.transport_codes.city_pair_distance_km", return_value=820.0
        ):
            issues = critic_program_issues(
                program,
                "tickets",
                origin_city="Москва",
                destination_city="Казань",
            )
        self.assertEqual(issues, [])

    def test_critic_tickets_short_route_no_plane_ok(self) -> None:
        program = {
            "tickets": (
                "**Поезд**: РЖД https://www.tutu.ru/poezda/Moskva/Tver/?date=10.08.2026 "
                "**Автобус**: Tutu https://bus.tutu.ru/raspisanie/gorod_Moskva/gorod_Tver/ "
                + "x" * 40
            ),
        }
        with (
            patch("search.transport_codes.city_pair_distance_km", return_value=180.0),
            patch("search.airport_routing.city_pair_distance_km", return_value=180.0),
        ):
            issues = critic_program_issues(
                program,
                "tickets",
                origin_city="Москва",
                destination_city="Тверь",
            )
        self.assertEqual(issues, [])

    def test_critic_tickets_short_route_requires_bus(self) -> None:
        program = {
            "tickets": (
                "**Поезд**: РЖД https://www.tutu.ru/poezda/Moskva/Tver/?date=10.08.2026 "
                + "x" * 40
            ),
        }
        with (
            patch("search.transport_codes.city_pair_distance_km", return_value=180.0),
            patch("search.airport_routing.city_pair_distance_km", return_value=180.0),
        ):
            issues = critic_program_issues(
                program,
                "tickets",
                origin_city="Москва",
                destination_city="Тверь",
            )
        self.assertTrue(any("автобус" in issue for issue in issues))


if __name__ == "__main__":
    unittest.main()
