"""Тесты тегов досуга для Яндекс.Карт."""

from __future__ import annotations

import unittest

from search.yandex.leisure_tags import (
    leisure_pool_limit,
    normalize_leisure_categories,
    search_text_for_tag,
)


class TestYandexLeisureTags(unittest.TestCase):
    def test_always_includes_landmarks(self) -> None:
        self.assertEqual(normalize_leisure_categories([]), ["landmarks"])
        self.assertEqual(normalize_leisure_categories(["museums"]), ["landmarks", "museums"])

    def test_drops_unknown_tags(self) -> None:
        self.assertEqual(
            normalize_leisure_categories(["museums", "unknown"]),
            ["landmarks", "museums"],
        )

    def test_pace_limits(self) -> None:
        self.assertEqual(leisure_pool_limit("relaxed"), 8)
        self.assertEqual(leisure_pool_limit("moderate"), 14)
        self.assertEqual(leisure_pool_limit("packed"), 20)

    def test_search_text_contains_city(self) -> None:
        text = search_text_for_tag("museums", "Казань")
        self.assertIn("Казань", text)
        self.assertIn("музей", text.lower())


if __name__ == "__main__":
    unittest.main()
