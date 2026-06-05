"""Тесты deferred HITL для веб-API."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from agents.nodes import human_review_node, route_after_human
from models.state import AgentState


class TestDeferredHitl(unittest.TestCase):
    def test_human_review_deferred_sets_review_status(self) -> None:
        state: AgentState = {
            "trip_id": 1,
            "review_mode": "deferred",
            "critic_notes": "",
        }
        with patch("agents.nodes.update_trip_status") as mock_status:
            result = human_review_node(state)
        mock_status.assert_called_once_with(1, "review")
        self.assertFalse(result["approved"])

    def test_route_after_human_deferred_ends(self) -> None:
        state: AgentState = {"review_mode": "deferred", "approved": False}
        self.assertEqual(route_after_human(state), "__end__")

    def test_route_after_human_cli_rebuild_loops(self) -> None:
        state: AgentState = {"review_mode": "cli", "approved": False}
        self.assertEqual(route_after_human(state), "researcher")


if __name__ == "__main__":
    unittest.main()
