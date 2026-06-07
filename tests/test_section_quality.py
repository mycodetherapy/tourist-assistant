"""Тесты качества секций и critic."""

from __future__ import annotations

import json
import unittest

from agents.critic import run_critic
from agents.section_quality import (
    critic_program_issues,
    is_garbage_section,
)
from langchain_core.messages import ToolMessage
from models.routes import (
    DiningOption,
    GeoPoint,
    PoiPoint,
    RouteMaterials,
    RouteProgram,
    RouteStop,
    TripRouteCase,
)
from agents.route_postprocess import finalize_route_program


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
                coordinates=GeoPoint(lon=49.1 + i * 0.01, lat=55.8),
                maps_url=f"https://yandex.ru/maps/org/l{i}",
            )
            for i in range(5)
        ],
        dining_options=[
            DiningOption(
                poi_id=f"d{i}",
                anchor_poi_id=f"l{i}",
                name=f"Ресторан {i}",
                coordinates=GeoPoint(lon=49.2 + i * 0.01, lat=55.81),
                maps_url=f"https://yandex.ru/maps/org/d{i}",
            )
            for i in range(3)
        ],
    )
    cases = []
    offsets = {"A": 0, "B": 2, "C": 4}
    for case_id, title in (("A", "A"), ("B", "B"), ("C", "C")):
        stops = []
        order = 1
        base = offsets[case_id]
        for j in range(3):
            i = (base + j) % 5
            stops.append(
                RouteStop(
                    order=order,
                    kind="leisure",
                    poi_id=f"l{i}",
                    narrative=f"Место {i}",
                )
            )
            order += 1
            stops.append(
                RouteStop(
                    order=order,
                    kind="dining",
                    poi_id=f"d{min(i, 2)}",
                    narrative=f"Ресторан {i}",
                )
            )
            order += 1
        cases.append(
            TripRouteCase(case_id=case_id, title=title, summary="тест", stops=stops)
        )
    program = finalize_route_program(RouteProgram(cases=cases), materials)
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


if __name__ == "__main__":
    unittest.main()
