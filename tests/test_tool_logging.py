"""Тесты parse_tool_result."""

from __future__ import annotations

import json
import unittest

from search.tool_logging import parse_tool_result


class TestToolLogging(unittest.TestCase):
    def test_parse_route_materials_payload(self) -> None:
        payload = json.dumps(
            {
                "category": "route_materials",
                "live_data": True,
                "leisure_count": 8,
                "provider": "osm",
            }
        )
        m = parse_tool_result(payload)
        self.assertTrue(m["live_data"])
        self.assertEqual(m["results_count"], 8)
        self.assertEqual(m["provider"], "osm")

    def test_parse_error_string(self) -> None:
        m = parse_tool_result("not json")
        self.assertFalse(m["live_data"])


if __name__ == "__main__":
    unittest.main()
