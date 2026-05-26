"""Тесты merge и scope без LLM."""

from __future__ import annotations

import unittest

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
            "transport": "old transport",
            "lifehacks": "old tips",
        }
        updated = {
            "tickets": "new tickets",
            "events": "new events",
            "dining": "new dining",
            "transport": "new transport",
            "lifehacks": "new tips",
        }
        merged = merge_program(base, updated, "dining")
        self.assertEqual(merged["dining"], "new dining")
        self.assertEqual(merged["tickets"], "old tickets")
        self.assertEqual(merged["events"], "old events")

    def test_lifehacks_no_tools(self) -> None:
        self.assertEqual(required_tools_for_scope("lifehacks"), [])

    def test_tickets_one_tool(self) -> None:
        tools = required_tools_for_scope("tickets")
        self.assertEqual(tools, ["search_roundtrip_tickets"])


if __name__ == "__main__":
    unittest.main()
