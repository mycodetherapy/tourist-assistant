"""Тесты critic без LLM."""

from __future__ import annotations

import unittest

from agents.critic import run_critic
from langchain_core.messages import ToolMessage


def _leisure_stops(case_id: str, count: int) -> list[dict]:
    return [
        {
            "order": i + 1,
            "kind": "leisure",
            "poi_id": f"poi:{case_id}:{i}",
            "narrative": f"Место {case_id}-{i}",
        }
        for i in range(count)
    ]


class TestCritic(unittest.TestCase):
    def test_passes_with_route_materials_and_routes(self) -> None:
        state = {
            "rebuild_scope": "full",
            "messages": [
                ToolMessage(content="{}", tool_call_id="1", name="search_route_materials"),
            ],
            "program": {
                "tickets": "",
                "routes": {
                    "cases": [
                        {
                            "case_id": "A",
                            "title": "A",
                            "summary": "",
                            "stops": _leisure_stops("A", 3),
                            "maps_route_url": "https://yandex.ru/maps/?rtext=1",
                        },
                        {
                            "case_id": "B",
                            "title": "B",
                            "summary": "",
                            "stops": _leisure_stops("B", 3),
                            "maps_route_url": "https://yandex.ru/maps/?rtext=2",
                        },
                        {
                            "case_id": "C",
                            "title": "C",
                            "summary": "",
                            "stops": _leisure_stops("C", 3),
                            "maps_route_url": "https://yandex.ru/maps/?rtext=3",
                        },
                    ]
                },
                "routes_text": "Маршруты A/B/C с достаточным описанием для critic и проверки минимальной длины текста.",
                "lifehacks": "",
                "city_fact_status": "pending",
            },
        }
        result = run_critic(state)
        self.assertTrue(result.passed, result.notes)

    def test_program_issues_retry_writer(self) -> None:
        state = {
            "rebuild_scope": "full",
            "messages": [
                ToolMessage(content="{}", tool_call_id="1", name="search_route_materials"),
            ],
            "program": {
                "routes": {"cases": []},
                "routes_text": "",
                "lifehacks": "x",
            },
        }
        result = run_critic(state)
        self.assertFalse(result.passed)
        self.assertEqual(result.retry_target, "writer")


if __name__ == "__main__":
    unittest.main()
