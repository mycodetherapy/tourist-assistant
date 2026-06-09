"""Тесты fuzzy-match discovery → POI pool."""

from __future__ import annotations

import unittest

from models.routes import GeoPoint, PoiPoint
from search.poi_match import match_names_to_pool, name_similarity


def _poi(name: str, poi_id: str) -> PoiPoint:
    return PoiPoint(
        poi_id=poi_id,
        tag="landmarks",
        name=name,
        coordinates=GeoPoint(lon=50.1, lat=53.2),
        maps_url="https://example.com",
    )


class TestPoiMatch(unittest.TestCase):
    def test_similarity_partial_match(self) -> None:
        self.assertGreater(name_similarity("Стела Ладья", "Стела «Ладья»"), 0.7)

    def test_match_names_to_pool(self) -> None:
        pool = [
            _poi("Музей модерна", "osm_1"),
            _poi("Самарская набережная", "osm_2"),
        ]
        matches = match_names_to_pool(["музей модерна", "набережная"], pool)
        self.assertEqual(len(matches), 2)
        self.assertEqual(matches[0].poi_id, "osm_1")


if __name__ == "__main__":
    unittest.main()
