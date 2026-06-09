"""Тесты поиска leisure через Geocoder без city seeds."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from search.yandex.leisure_search import search_leisure_points


class TestLeisureSearch(unittest.TestCase):
    @patch("search.yandex.leisure_search.get_api_key", return_value=True)
    @patch("search.yandex.landmark_discovery.discover_landmark_names")
    @patch("search.yandex.leisure_search.geocode_city")
    @patch("search.yandex.leisure_search.geocode_places")
    def test_collects_from_discovery_then_geocoder(
        self,
        geocode_places,
        geocode_city,
        discover_landmark_names,
        _key,
    ) -> None:
        geocode_city.return_value = (40.93, 57.77, (0.1, 0.08))
        discover_landmark_names.return_value = ["Сусанинская площадь"]
        geocode_places.return_value = [
            {
                "geometry": {"coordinates": [40.927155, 57.768072]},
                "properties": {
                    "CompanyMetaData": {
                        "name": "Сусанинская площадь",
                        "address": "Сусанинская площадь, Кострома, Россия",
                        "url": "https://yandex.ru/maps/?text=sq",
                    }
                },
            },
        ]
        points = search_leisure_points(city="Кострома", categories=["landmarks"], pace="relaxed")
        names = [p.name for p in points]
        self.assertTrue(any("Сусанинская" in n for n in names))
        discover_landmark_names.assert_called_once_with("Кострома")
        self.assertGreaterEqual(geocode_places.call_count, 1)


if __name__ == "__main__":
    unittest.main()
