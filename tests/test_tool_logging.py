"""Тесты parse_tool_result."""

from __future__ import annotations

import json
import unittest

from search.tool_logging import parse_tool_result


class TestToolLogging(unittest.TestCase):
    def test_parse_tickets_payload(self) -> None:
        payload = json.dumps(
            {
                "live_data": True,
                "results_count": 5,
                "raw_results_count": 7,
                "search_provider": "ddgs",
            }
        )
        m = parse_tool_result(payload)
        self.assertTrue(m["live_data"])
        self.assertEqual(m["results_count"], 5)

    def test_parse_error_string(self) -> None:
        m = parse_tool_result("not json")
        self.assertFalse(m["live_data"])


if __name__ == "__main__":
    unittest.main()
