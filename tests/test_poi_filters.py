"""Тесты фильтрации POI и URL маршрутов с названиями."""

from __future__ import annotations

import unittest
from urllib.parse import unquote

from models.routes import GeoPoint
from search.yandex.poi_filters import is_acceptable_place_name, is_transport_hub
from search.yandex.route_url import build_maps_route_url


class TestPoiFilters(unittest.TestCase):
    def test_rejects_transport_hubs(self) -> None:
        self.assertTrue(is_transport_hub("станция Кострома"))
        self.assertTrue(is_transport_hub("аэропорт Кострома (Сокеркино)"))
        self.assertFalse(is_acceptable_place_name("станция Кострома"))
        self.assertFalse(is_acceptable_place_name("Центральный район"))

    def test_accepts_landmarks(self) -> None:
        self.assertTrue(is_acceptable_place_name("Сусанинская площадь"))
        self.assertTrue(is_acceptable_place_name("Кафе Огонёк"))

    def test_route_url_uses_coordinates(self) -> None:
        url = build_maps_route_url(
            [
                GeoPoint(lon=40.927155, lat=57.768072),
                GeoPoint(lon=40.9263, lat=57.7672),
            ],
            transport="walking",
        )
        decoded = unquote(url)
        self.assertIn("rtext=", url)
        self.assertIn("57.768072,40.927155", decoded)
        self.assertIn("57.7672,40.9263", decoded)
        self.assertIn("rtt=pd", url)
        self.assertNotIn("Кафе", url)


if __name__ == "__main__":
    unittest.main()
