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

    def test_wikidata_accepts_english_museum_name(self) -> None:
        poi = wikidata_row_to_poi(
            qid="Q12345",
            name="Istanbul Archaeology Museums",
            coord_literal="Point(28.98 41.01)",
            city_hint="Стамбул",
        )
        self.assertIsNotNone(poi)
        assert poi is not None
        self.assertEqual(poi.tag, "museums")

    def test_pedestrian_street_from_osm(self) -> None:
        poi = osm_element_to_poi(
            {
                "type": "way",
                "id": 1001,
                "center": {"lat": 56.326, "lon": 44.006},
                "tags": {
                    "name": "улица Баумана",
                    "highway": "pedestrian",
                },
            },
            city_hint="Казань",
        )
        self.assertIsNotNone(poi)
        assert poi is not None
        self.assertEqual(poi.tag, "pedestrian_streets")
        self.assertEqual(poi.name, "улица Баумана")

    def test_temple_from_osm(self) -> None:
        poi = osm_element_to_poi(
            {
                "type": "node",
                "id": 77,
                "lat": 56.328,
                "lon": 44.002,
                "tags": {
                    "name": "Петропавловский собор",
                    "building": "cathedral",
                },
            },
            city_hint="Казань",
        )
        self.assertIsNotNone(poi)
        assert poi is not None
        self.assertEqual(poi.tag, "temples")


if __name__ == "__main__":
    unittest.main()
