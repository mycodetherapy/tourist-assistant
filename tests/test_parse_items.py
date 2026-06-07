"""Тесты разбора программы на пункты."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from program.parse_items import parse_program_sections, parse_section

_FIXTURE = Path(__file__).resolve().parent.parent / "eval/fixtures/msk_weekend_smoke_program.json"


class TestParseItems(unittest.TestCase):
    def test_smoke_fixture_tickets(self) -> None:
        program = json.loads(_FIXTURE.read_text(encoding="utf-8"))
        section = parse_section("tickets", program["tickets"])
        self.assertIn("Маршрут:", section.intro)
        self.assertEqual(len(section.items), 3)
        self.assertTrue(section.items[0].startswith("- Aviasales"))

    def test_smoke_fixture_events_lines(self) -> None:
        program = json.loads(_FIXTURE.read_text(encoding="utf-8"))
        section = parse_section("events", program["events"])
        self.assertEqual(len(section.items), 2)
        self.assertIn("Третьяковская", section.items[0])

    def test_smoke_fixture_dining_numbered(self) -> None:
        program = json.loads(_FIXTURE.read_text(encoding="utf-8"))
        section = parse_section("dining", program["dining"])
        self.assertEqual(len(section.items), 7)
        self.assertTrue(section.items[0].startswith("1."))

    def test_lifehacks_paragraph(self) -> None:
        section = parse_section("lifehacks", "Утро: музей → обед рядом.")
        self.assertEqual(section.items, ("Утро: музей → обед рядом.",))

    def test_lifehacks_bullets(self) -> None:
        text = "- Совет один\n- Совет два"
        section = parse_section("lifehacks", text)
        self.assertEqual(len(section.items), 2)

    def test_events_numbered_after_district_intro(self) -> None:
        text = (
            "Центр, Китай-город и Замоскворечье\n"
            "1. [Музей A](https://example.com/a)\n"
            "2. [Музей B](https://example.com/b)"
        )
        section = parse_section("events", text)
        self.assertEqual(section.intro, "Центр, Китай-город и Замоскворечье")
        self.assertEqual(len(section.items), 2)
        self.assertTrue(section.items[0].startswith("1."))
        self.assertTrue(section.items[1].startswith("2."))

    def test_lifehacks_numbered_list(self) -> None:
        text = "1. Совет один\n2. Совет два\n3. Совет три"
        section = parse_section("lifehacks", text)
        self.assertEqual(len(section.items), 3)
        self.assertTrue(section.items[0].startswith("1."))

    def test_parse_program_sections_keys(self) -> None:
        program = {
            "tickets": "intro\n- билет",
            "events": "1. музей",
            "dining": "1. кафе",
            "lifehacks": "- совет",
        }
        parsed = parse_program_sections(program)
        self.assertEqual(len(parsed.tickets.items), 1)
        self.assertEqual(len(parsed.events.items), 1)

    def test_parse_routes_structured(self) -> None:
        program = {
            "routes": {
                "cases": [
                    {
                        "case_id": "A",
                        "title": "Классика",
                        "summary": "Кратко",
                        "maps_route_url": "https://yandex.ru/maps/?rtext=1",
                        "stops": [
                            {"order": 1, "kind": "leisure", "narrative": "Музей", "time_hint": "утро"}
                        ],
                    }
                ]
            },
            "routes_text": "Пул мест\n\n## Вариант A: Классика",
            "tickets": "",
            "lifehacks": "",
        }
        parsed = parse_program_sections(program)
        self.assertEqual(len(parsed.routes.items), 1)
        self.assertIn("Классика", parsed.routes.items[0])
        self.assertEqual(len(parsed.events.items), 0)


if __name__ == "__main__":
    unittest.main()
