"""Тесты free-tier deterministic pipeline."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from services.deterministic_runner import run_deterministic_build


class DeterministicRunnerTests(unittest.TestCase):
    @patch("services.saas_events.usage_from_graph_run")
    @patch("services.deterministic_runner.FinalProgram")
    @patch("services.deterministic_runner.save_itinerary_version", return_value=42)
    @patch("services.deterministic_runner.log_agent_run")
    @patch("services.deterministic_runner.get_trip", return_value={"user_id": 1})
    @patch("services.deterministic_runner.repair_program_routes", side_effect=lambda p, **_: p)
    @patch("services.deterministic_runner.resolve_routes_program")
    @patch("services.deterministic_runner._invoke_route_materials")
    def test_routes_scope_skips_fresh_search(
        self,
        mock_invoke,
        mock_resolve,
        _repair,
        _trip,
        _log,
        _save,
        mock_final,
        _usage,
    ) -> None:
        mock_final.model_validate.return_value.model_dump.return_value = {
            "routes_text": "x",
            "lifehacks": "tip",
        }
        mock_routes = MagicMock()
        mock_routes.model_dump.return_value = {"cases": []}
        mock_resolve.return_value = (mock_routes, "## Вариант A")
        state = {
            "trip_id": 1,
            "city": "Казань",
            "dates": "2 дня",
            "rebuild_scope": "routes",
            "preferences": {"pace": "moderate", "transport_preference": "mixed"},
            "base_program": {"routes_text": "old", "lifehacks": "tip", "city_fact_status": "ready"},
            "messages": [],
        }
        run_deterministic_build(state)
        mock_invoke.assert_not_called()
        mock_resolve.assert_called_once()
