"""Тесты сбора per-node метрик прогона графа."""

from __future__ import annotations

import json
import os
import tempfile
import unittest

from db import init_db, list_agent_runs, log_agent_run
from services.graph_metrics import GraphRunMetrics


class TestGraphRunMetrics(unittest.TestCase):
    def test_to_dict_nodes_and_tools(self) -> None:
        metrics = GraphRunMetrics()
        metrics.record_node("researcher", 3.5, cumulative_sec=3.5)
        metrics.record_node("executor", 1.2, cumulative_sec=4.7)
        metrics.record_node("writer", 20.0, cumulative_sec=24.7)
        metrics.record_tool("search_roundtrip_tickets", 0.3)
        metrics.record_tool("search_route_materials", 1.1)

        data = metrics.to_dict()
        self.assertEqual(data["nodes"]["writer"]["total_ms"], 20000)
        self.assertEqual(data["nodes"]["researcher"]["count"], 1)
        self.assertEqual(len(data["timeline"]), 3)
        self.assertEqual(data["tools"]["search_route_materials"]["total_ms"], 1100)

    def test_log_agent_run_stores_node_timings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["DATABASE_PATH"] = os.path.join(tmp, "test.db")
            init_db()
            from db.repository import create_trip

            trip_id = create_trip("Москва", "1-3 июля 2026", "Казань", "тест")
            timings = {
                "nodes": {"writer": {"count": 1, "total_ms": 5000}},
                "timeline": [],
            }
            log_agent_run(
                trip_id,
                run_id="test-run",
                rebuild_scope="full",
                duration_ms=9000,
                node_timings=timings,
            )
            rows = list_agent_runs(limit=1)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["node_timings"], timings)


if __name__ == "__main__":
    unittest.main()
