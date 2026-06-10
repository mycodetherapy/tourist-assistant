"""Тесты геокодинга городов (Nominatim) и зарубежных направлений."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from search.city_codes import geocode_place_queries, is_foreign_destination
from search.osm.nominatim import resolve_city_center


class TestGeocodePlaceQueries(unittest.TestCase):
    def test_istanbul_without_russia_suffix(self) -> None:
        self.assertTrue(is_foreign_destination("Стамбул"))
        self.assertEqual(geocode_place_queries("Стамбул"), ("Стамбул",))

    def test_kazan_tries_russia_fallback(self) -> None:
        self.assertFalse(is_foreign_destination("Казань"))
        self.assertEqual(geocode_place_queries("Казань"), ("Казань", "Казань, Россия"))


class TestNominatimPickBest(unittest.TestCase):
    def test_moscow_prefers_city_over_admin_boundary(self) -> None:
        from search.osm.nominatim import _pick_best_nominatim_item

        items = [
            {
                "category": "boundary",
                "type": "administrative",
                "addresstype": "state",
                "importance": 0.87,
                "place_rank": 8,
                "lat": "55.6255780",
                "lon": "37.6063916",
            },
            {
                "category": "place",
                "type": "city",
                "addresstype": "city",
                "importance": 0.87,
                "place_rank": 15,
                "lat": "55.7505412",
                "lon": "37.6174782",
            },
        ]
        best = _pick_best_nominatim_item(items)
        self.assertIsNotNone(best)
        assert best is not None
        self.assertEqual(best["lat"], "55.7505412")


class TestResolveCityCenter(unittest.TestCase):
    @patch("search.osm.nominatim._search_nominatim")
    def test_istanbul_found_on_bare_query(self, search) -> None:
        from search.osm.nominatim import CityCenter

        search.side_effect = [
            CityCenter(
                city="Стамбул",
                lon=28.97,
                lat=41.01,
                bbox=(28.5, 40.8, 29.5, 41.3),
                wikidata_id="Q406",
                display_name="Istanbul, Turkey",
            ),
        ]
        center = resolve_city_center("Стамбул")
        self.assertIsNotNone(center)
        assert center is not None
        self.assertEqual(center.city, "Стамбул")
        self.assertEqual(center.wikidata_id, "Q406")
        search.assert_called_once_with("Стамбул")

    @patch("search.osm.nominatim._search_nominatim")
    def test_russian_city_falls_back_to_russia_suffix(self, search) -> None:
        from search.osm.nominatim import CityCenter

        search.side_effect = [
            None,
            CityCenter(
                city="Омск",
                lon=73.37,
                lat=54.99,
                bbox=(73.0, 54.8, 73.7, 55.2),
            ),
        ]
        center = resolve_city_center("Омск")
        self.assertIsNotNone(center)
        self.assertEqual(search.call_count, 2)
        self.assertEqual(search.call_args_list[0].args[0], "Омск")
        self.assertEqual(search.call_args_list[1].args[0], "Омск, Россия")


if __name__ == "__main__":
    unittest.main()
