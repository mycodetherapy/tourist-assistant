"""Маршрутизация после executor."""

from __future__ import annotations

import json
import unittest

from agents.nodes import route_after_executor
from langchain_core.messages import ToolMessage


class TestRouteAfterExecutor(unittest.TestCase):
    def test_ready_goes_to_writer(self) -> None:
        payload = json.dumps(
            {
                "category": "route_materials",
                "provider": "osm",
                "leisure_count": 3,
                "materials": {
                    "provider": "osm",
                    "city": "Казань",
                    "dates": "июль",
                    "leisure_points": [
                        {
                            "poi_id": "p1",
                            "tag": "landmarks",
                            "name": "A",
                            "coordinates": {"lon": 49.1, "lat": 55.7},
                            "maps_url": "https://yandex.ru/maps/org/a",
                        }
                    ],
                    "dining_options": [],
                },
            }
        )
        state = {
            "rebuild_scope": "full",
            "messages": [
                ToolMessage(
                    content=payload,
                    tool_call_id="1",
                    name="search_route_materials",
                )
            ],
        }
        self.assertEqual(route_after_executor(state), "writer")

    def test_missing_tool_goes_to_researcher(self) -> None:
        state = {"rebuild_scope": "full", "messages": []}
        self.assertEqual(route_after_executor(state), "researcher")


if __name__ == "__main__":
    unittest.main()
