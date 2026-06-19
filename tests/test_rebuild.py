"""Тесты merge и scope без LLM."""

from __future__ import annotations

import unittest

from models.schemas import normalize_stored_program
from planning.rebuild import (
    merge_program,
    required_tools_for_scope,
)


class TestRebuild(unittest.TestCase):
    def test_merge_partial_routes(self) -> None:
        base = {
            "routes": {"cases": []},
            "routes_text": "old routes",
            "lifehacks": "old tips",
        }
        updated = {
            "routes": {"cases": [{"case_id": "A"}]},
            "routes_text": "new routes",
            "lifehacks": "new tips",
        }
        merged = merge_program(base, updated, "routes")
        self.assertEqual(merged["routes_text"], "new routes")
        self.assertEqual(merged["lifehacks"], "old tips")

    def test_normalize_strips_transport(self) -> None:
        raw = {
            "routes_text": "r",
            "lifehacks": "l",
            "transport": "x",
        }
        norm = normalize_stored_program(raw)
        self.assertNotIn("transport", norm)

    def test_lifehacks_no_tools(self) -> None:
        self.assertEqual(required_tools_for_scope("lifehacks"), [])

    def test_routes_no_tools(self) -> None:
        tools = required_tools_for_scope("routes")
        self.assertEqual(tools, [])

    def test_full_uses_route_materials(self) -> None:
        tools = required_tools_for_scope("full")
        self.assertEqual(tools, ["search_route_materials"])


if __name__ == "__main__":
    unittest.main()
