"""Тесты тегов досуга для Яндекс.Карт."""

from __future__ import annotations

import unittest

from search.yandex.leisure_tags import (
    DEFAULT_GEOCODER_TAGS,
    default_geocoder_tags,
    geocode_queries_for_tag,
    leisure_pool_limit,
    leisure_search_pool_limit,
    search_text_for_tag,
)


class TestYandexLeisureTags(unittest.TestCase):
    def test_default_geocoder_tags(self) -> None:
        tags = default_geocoder_tags()
        self.assertEqual(tags, list(DEFAULT_GEOCODER_TAGS))
        self.assertIn("landmarks", tags)
        self.assertIn("parks", tags)
        self.assertNotIn("embankments", tags)

    def test_pace_limits(self) -> None:
        self.assertEqual(leisure_pool_limit("relaxed"), 8)
        self.assertEqual(leisure_pool_limit("moderate"), 14)
        self.assertEqual(leisure_pool_limit("packed"), 20)

    def test_search_pool_limit_fixed(self) -> None:
        self.assertEqual(leisure_search_pool_limit(), 50)

    def test_search_text_contains_city(self) -> None:
        text = search_text_for_tag("museums", "Казань")
        self.assertIn("Казань", text)
        self.assertIn("музей", text.lower())

    def test_infer_temple_and_pedestrian_tags(self) -> None:
        from search.yandex.leisure_tags import infer_leisure_tag

        self.assertEqual(infer_leisure_tag("Благовещенский собор"), "temples")
        self.assertEqual(infer_leisure_tag("Большая Покровская улица"), "pedestrian_streets")
        self.assertEqual(infer_leisure_tag("улица Баумана"), "pedestrian_streets")

    def test_geocode_queries_for_tag(self) -> None:
        queries = geocode_queries_for_tag("parks", "Казань")
        self.assertGreaterEqual(len(queries), 2)
        self.assertTrue(any("Казань" in q for q in queries))


if __name__ == "__main__":
    unittest.main()
