"""Тесты merge и scope без LLM."""

from __future__ import annotations

import unittest

from models.schemas import normalize_stored_program
from planning.rebuild import (
    merge_program,
    required_tools_for_scope,
)


class TestRebuild(unittest.TestCase):
    def test_merge_partial_dining(self) -> None:
        base = {
            "tickets": "old tickets",
            "events": "old events",
            "dining": "old dining",
            "transport": "legacy transport",
            "lifehacks": "old tips",
        }
        updated = {
            "tickets": "new tickets",
            "events": "new events",
            "dining": "new dining",
            "lifehacks": "new tips",
        }
        merged = merge_program(base, updated, "dining")
        self.assertEqual(merged["dining"], "new dining")
        self.assertEqual(merged["tickets"], "old tickets")
        self.assertNotIn("transport", merged)

    def test_normalize_strips_transport(self) -> None:
        raw = {"tickets": "t", "events": "e", "dining": "d", "transport": "x", "lifehacks": "l"}
        norm = normalize_stored_program(raw)
        self.assertNotIn("transport", norm)

    def test_lifehacks_no_tools(self) -> None:
        self.assertEqual(required_tools_for_scope("lifehacks"), [])

    def test_dining_tool_name(self) -> None:
        tools = required_tools_for_scope("dining")
        self.assertEqual(tools, ["search_dining"])

    def test_tickets_one_tool(self) -> None:
        tools = required_tools_for_scope("tickets")
        self.assertEqual(tools, ["search_roundtrip_tickets"])


if __name__ == "__main__":
    unittest.main()
