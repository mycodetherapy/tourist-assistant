"""Тесты детерминированной готовности tools."""

from __future__ import annotations

import json
import unittest

from langchain_core.messages import ToolMessage

from planning.tools_readiness import (
    evaluate_materials_tool,
    evaluate_tools_readiness,
)


def _materials_payload(
    *,
    leisure_count: int = 5,
    provider: str = "osm",
    demo: bool = False,
    warnings: list[str] | None = None,
) -> str:
    points = []
    for i in range(leisure_count):
        maps_url = (
            f"https://yandex.ru/maps/org/demo_landmarks/{i}"
            if demo
            else f"https://yandex.ru/maps/org/poi_{i}"
        )
        points.append(
            {
                "poi_id": f"poi_{i}",
                "tag": "landmarks",
                "name": f"Place {i}",
                "coordinates": {"lon": 49.1 + i * 0.01, "lat": 55.7},
                "maps_url": maps_url,
            }
        )
    payload = {
        "category": "route_materials",
        "provider": provider,
        "leisure_count": leisure_count,
        "materials": {
            "provider": provider,
            "city": "Казань",
            "dates": "июль",
            "leisure_points": points,
            "dining_options": [],
        },
    }
    if warnings:
        payload["warnings"] = warnings
        payload["warning"] = warnings[0]
    return json.dumps(payload, ensure_ascii=False)


class TestToolsReadiness(unittest.TestCase):
    def test_ok_payload_ready(self) -> None:
        result = evaluate_materials_tool(_materials_payload())
        self.assertTrue(result.ready)
        self.assertFalse(result.reason)

    def test_json_error_not_ready(self) -> None:
        result = evaluate_materials_tool('{"error": "bad city"}')
        self.assertFalse(result.ready)

    def test_exception_text_not_ready(self) -> None:
        result = evaluate_materials_tool("Ошибка выполнения инструмента x: boom")
        self.assertFalse(result.ready)

    def test_empty_leisure_not_ready(self) -> None:
        result = evaluate_materials_tool(_materials_payload(leisure_count=0))
        self.assertFalse(result.ready)
        self.assertIn("leisure_count", result.reason or "")

    def test_fallback_ready_with_warning(self) -> None:
        result = evaluate_materials_tool(
            _materials_payload(provider="fallback", demo=True)
        )
        self.assertTrue(result.ready)
        self.assertTrue(result.warnings)
        self.assertIn("Реальные места не найдены", result.warnings[0])

    def test_full_scope_ready_after_tool(self) -> None:
        state = {
            "rebuild_scope": "full",
            "messages": [
                ToolMessage(
                    content=_materials_payload(),
                    tool_call_id="1",
                    name="search_route_materials",
                )
            ],
        }
        result = evaluate_tools_readiness(state)
        self.assertTrue(result.ready)

    def test_full_scope_missing_tool_not_ready(self) -> None:
        state = {"rebuild_scope": "full", "messages": []}
        result = evaluate_tools_readiness(state)
        self.assertFalse(result.ready)

    def test_routes_scope_ready_without_tool(self) -> None:
        state = {"rebuild_scope": "routes", "messages": []}
        result = evaluate_tools_readiness(state)
        self.assertTrue(result.ready)


if __name__ == "__main__":
    unittest.main()
