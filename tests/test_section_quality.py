"""Тесты качества секций и critic."""

from __future__ import annotations

import json
import unittest

from agents.critic import run_critic
from agents.section_quality import (
    critic_program_issues,
    is_garbage_section,
    resolve_text_section,
)
from langchain_core.messages import ToolMessage


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

    def test_critic_fails_garbage_events_scope(self) -> None:
        state = {
            "rebuild_scope": "events",
            "messages": [
                ToolMessage(content="{}", tool_call_id="1", name="search_culture_events"),
            ],
            "program": {
                "events": ":[{",
                "tickets": "ok",
                "dining": "x",
                "lifehacks": "x",
            },
        }
        passed, notes = run_critic(state)
        self.assertFalse(passed)
        self.assertIn("events", notes)

    def test_resolve_events_from_digest(self) -> None:
        payload = {
            "digest": (
                "Музей А — выставки https://a.ru\n"
                "Музей B — постоянная экспозиция https://b.ru\n"
                "Музей C — афиша https://c.ru\n"
            ),
            "live_data": True,
        }
        messages = [
            ToolMessage(
                content=json.dumps(payload, ensure_ascii=False),
                tool_call_id="1",
                name="search_culture_events",
            )
        ]
        resolved = resolve_text_section(
            "events",
            ":[{",
            messages=messages,
            base_program=None,
            tool_name="search_culture_events",
        )
        self.assertIn("](https://a.ru)", resolved)
        self.assertFalse(is_garbage_section(resolved, "events"))

    def test_critic_program_issues_events_links(self) -> None:
        issues = critic_program_issues(
            {"events": "коротко"},
            "events",
        )
        self.assertTrue(any("ссылок" in i or "JSON" in i or "пуст" in i for i in issues))

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
