"""Тесты parse_tool_result."""

from __future__ import annotations

import json
import unittest

from search.tool_logging import parse_tool_result


class TestToolLogging(unittest.TestCase):
    def test_parse_tickets_payload_v1(self) -> None:
        payload = json.dumps(
            {
                "schema_version": "1",
                "category": "tickets",
                "live_data": True,
                "offers_count": 8,
                "results_count": 8,
            }
        )
        m = parse_tool_result(payload)
        self.assertTrue(m["live_data"])
        self.assertEqual(m["results_count"], 8)
        self.assertEqual(m["provider"], "deep_links")

    def test_parse_tickets_payload_travelpayouts(self) -> None:
        payload = json.dumps(
            {
                "schema_version": "1",
                "category": "tickets",
                "live_data": True,
                "offers_count": 3,
                "avia_api_status": "ok",
            }
        )
        m = parse_tool_result(payload)
        self.assertEqual(m["provider"], "travelpayouts")

    def test_parse_error_string(self) -> None:
        m = parse_tool_result("not json")
        self.assertFalse(m["live_data"])


if __name__ == "__main__":
    unittest.main()
