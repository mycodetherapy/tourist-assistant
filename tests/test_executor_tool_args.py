"""Тесты подстановки city/dates в tool args из state."""

from __future__ import annotations

import unittest

from agents.nodes import resolve_tool_args
from langchain_core.messages import HumanMessage


class TestExecutorToolArgs(unittest.TestCase):
    def test_overrides_route_materials_city(self) -> None:
        state = {
            "city": "Самара",
            "dates": "20-21 июня 2026",
            "origin_city": "Москва",
            "messages": [HumanMessage(content="test")],
        }
        args = resolve_tool_args(
            state,
            "search_route_materials",
            {"city": "Йошкар-Ола", "dates": "wrong"},
        )
        self.assertEqual(args["city"], "Самара")
        self.assertEqual(args["dates"], "20-21 июня 2026")

    def test_overrides_tickets_cities(self) -> None:
        state = {
            "city": "Самара",
            "dates": "20-21 июня 2026",
            "origin_city": "Москва",
            "messages": [],
        }
        args = resolve_tool_args(
            state,
            "search_roundtrip_tickets",
            {
                "origin_city": "Казань",
                "destination_city": "Йошкар-Ола",
                "dates": "wrong",
            },
        )
        self.assertEqual(args["origin_city"], "Москва")
        self.assertEqual(args["destination_city"], "Самара")
        self.assertEqual(args["dates"], "20-21 июня 2026")


if __name__ == "__main__":
    unittest.main()
