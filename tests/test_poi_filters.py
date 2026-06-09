"""Тесты фильтрации POI и URL маршрутов с названиями."""

from __future__ import annotations

import unittest
from urllib.parse import unquote

from models.routes import GeoPoint
from search.yandex.poi_filters import (
    is_acceptable_place_name,
    is_generic_street_name,
    is_landmark_poi_name,
    is_transport_hub,
    route_name_key,
)
from search.yandex.route_url import build_maps_route_url


class TestPoiFilters(unittest.TestCase):
    def test_rejects_transport_hubs(self) -> None:
        self.assertTrue(is_transport_hub("станция Кострома"))
        self.assertTrue(is_transport_hub("аэропорт Кострома (Сокеркино)"))
        self.assertFalse(is_acceptable_place_name("станция Кострома"))
        self.assertFalse(is_acceptable_place_name("метро Площадь Революции"))
        self.assertFalse(is_acceptable_place_name("Центральный район"))

    def test_accepts_landmarks(self) -> None:
        self.assertTrue(is_acceptable_place_name("Сусанинская площадь"))
        self.assertTrue(is_acceptable_place_name("Кафе Огонёк"))

    def test_route_name_key_strips_street_prefix(self) -> None:
        self.assertEqual(
            route_name_key("улица Красные Ряды"),
            route_name_key("Красные Ряды"),
        )
        self.assertEqual(
            route_name_key("улица Красные Ряды, 1кИ"),
            route_name_key("Красные Ряды"),
        )

    def test_rejects_generic_streets(self) -> None:
        self.assertTrue(is_generic_street_name("улица Красные Ряды"))
        self.assertTrue(is_generic_street_name("улица Красные Ряды, 1кИ"))
        self.assertTrue(is_generic_street_name("Верхне-Набережная улица"))
        self.assertFalse(is_landmark_poi_name("улица Красные Ряды"))
        self.assertTrue(is_landmark_poi_name("Сусанинская площадь"))
        self.assertTrue(is_landmark_poi_name("Торговые ряды"))
        self.assertTrue(is_landmark_poi_name("Богоявленско-Анастасин монастырь"))
        self.assertTrue(is_landmark_poi_name("набережная Брюгге"))

    def test_accepts_named_embankment_geo_member(self) -> None:
        from search.yandex.poi_filters import is_acceptable_geo_member

        member = {
            "GeoObject": {
                "name": "набережная Брюгге",
                "Point": {"pos": "47.89 56.63"},
                "metaDataProperty": {
                    "GeocoderMetaData": {
                        "kind": "street",
                        "text": "Россия, Республика Марий Эл, Йошкар-Ола, набережная Брюгге",
                    }
                },
            }
        }
        self.assertTrue(
            is_acceptable_geo_member(member, city_hint="Йошкар-Ола")
        )

    def test_route_url_uses_coordinates(self) -> None:
        url = build_maps_route_url(
            [
                GeoPoint(lon=40.927155, lat=57.768072),
                GeoPoint(lon=40.9263, lat=57.7672),
            ],
            labels=["Сусанинская площадь", "Пожарная каланча"],
            city="Кострома",
            transport="walking",
        )
        decoded = unquote(url)
        self.assertIn("rtext=", url)
        self.assertIn("57.768072,40.927155", decoded)
        self.assertIn("57.7672,40.9263", decoded)
        self.assertIn("mode=routes", url)
        self.assertIn("rtt=pd", url)
        self.assertNotIn("Сусанинская", decoded)

    def test_route_url_always_pedestrian_even_for_taxi_pref(self) -> None:
        url = build_maps_route_url(
            [
                GeoPoint(lon=50.1, lat=53.2),
                GeoPoint(lon=50.11, lat=53.21),
            ],
            transport="taxi",
        )
        self.assertIn("rtt=pd", url)
        self.assertNotIn("rtt=auto", url)

    def test_rejects_city_only_name(self) -> None:
        from search.yandex.poi_filters import is_city_only_name

        self.assertTrue(is_city_only_name("Кострома", city_hint="Кострома"))
        self.assertFalse(is_landmark_poi_name("Кострома", city_hint="Кострома"))
        self.assertTrue(is_landmark_poi_name("Сусанинская площадь", city_hint="Кострома"))


if __name__ == "__main__":
    unittest.main()
