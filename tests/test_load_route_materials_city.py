"""Materials из tool игнорируются, если city не совпадает с поездкой."""

from __future__ import annotations

import json
import unittest

from langchain_core.messages import ToolMessage

from agents.finalize_helpers import load_route_materials


class TestLoadRouteMaterialsCity(unittest.TestCase):
    def test_rejects_mismatched_city(self) -> None:
        messages = [
            ToolMessage(
                content=json.dumps(
                    {
                        "materials": {
                            "schema_version": 1,
                            "provider": "yandex_maps",
                            "city": "Йошкар-Ола",
                            "dates": "июнь",
                            "leisure_points": [],
                            "dining_options": [],
                        }
                    },
                    ensure_ascii=False,
                ),
                tool_call_id="m",
                name="search_route_materials",
            ),
        ]
        self.assertIsNone(
            load_route_materials(messages, expected_city="Самара"),
        )

    def test_accepts_matching_city(self) -> None:
        messages = [
            ToolMessage(
                content=json.dumps(
                    {
                        "materials": {
                            "schema_version": 1,
                            "provider": "yandex_maps",
                            "city": "Самара",
                            "dates": "июнь",
                            "leisure_points": [],
                            "dining_options": [],
                        }
                    },
                    ensure_ascii=False,
                ),
                tool_call_id="m",
                name="search_route_materials",
            ),
        ]
        materials = load_route_materials(messages, expected_city="Самара")
        self.assertIsNotNone(materials)
        self.assertEqual(materials.city, "Самара")


if __name__ == "__main__":
    unittest.main()
