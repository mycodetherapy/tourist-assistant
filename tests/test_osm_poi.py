"""Тесты парсинга OSM/Wikidata в PoiPoint."""

from __future__ import annotations

import unittest

from search.osm.poi_from_tags import osm_element_to_poi, wikidata_row_to_poi


class TestOsmPoiFromTags(unittest.TestCase):
    def test_osm_node_with_ru_name(self) -> None:
        poi = osm_element_to_poi(
            {
                "type": "node",
                "id": 42,
                "lat": 53.2,
                "lon": 50.15,
                "tags": {
                    "name:ru": "Музей модерна",
                    "tourism": "museum",
                },
            },
            city_hint="Самара",
        )
        self.assertIsNotNone(poi)
        assert poi is not None
        self.assertEqual(poi.poi_id, "osm_node_42")
        self.assertEqual(poi.tag, "museums")

    def test_wikidata_coord(self) -> None:
        poi = wikidata_row_to_poi(
            qid="Q123",
            name="Стела «Ладья»",
            coord_literal="Point(50.12 53.20)",
            city_hint="Самара",
        )
        self.assertIsNotNone(poi)
        assert poi is not None
        self.assertEqual(poi.coordinates.lon, 50.12)


if __name__ == "__main__":
    unittest.main()
