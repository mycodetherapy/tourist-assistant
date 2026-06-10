"""Тесты фильтрации POI и URL маршрутов с названиями."""

from __future__ import annotations

import unittest
from urllib.parse import unquote

from models.routes import GeoPoint
from search.yandex.poi_filters import (
    is_acceptable_place_name,
    is_embankment_poi_name,
    is_generic_street_name,
    is_landmark_poi_name,
    is_transport_hub,
    poi_name_conflict,
    route_name_key,
    wikidata_poi_name_conflict,
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
        self.assertTrue(is_landmark_poi_name("Волжская набережная"))
        self.assertTrue(is_landmark_poi_name("Мечеть аль-Марджани", city_hint="Казань"))

    def test_accepts_pedestrian_streets_by_tag(self) -> None:
        from models.routes import PoiPoint
        from search.yandex.poi_filters import is_leisure_route_poi

        poi = PoiPoint(
            poi_id="osm_way_1",
            tag="pedestrian_streets",
            name="улица Баумана",
            coordinates=GeoPoint(lon=49.12, lat=55.79),
            maps_url="https://example.com",
        )
        self.assertTrue(is_leisure_route_poi(poi, city_hint="Казань"))
        poi_pokrov = poi.model_copy(
            update={"name": "Большая Покровская улица", "poi_id": "osm_way_2"}
        )
        self.assertTrue(is_leisure_route_poi(poi_pokrov, city_hint="Нижний Новгород"))

    def test_embankment_name_accepted(self) -> None:
        self.assertTrue(is_embankment_poi_name("Волжская набережная", city_hint="Самара"))
        self.assertTrue(is_embankment_poi_name("набережная Казанки", city_hint="Казань"))
        self.assertFalse(is_embankment_poi_name("Верхне-Набережная улица"))

    def test_relaxed_wikidata_conflict_only_exact_name_key(self) -> None:
        a = GeoPoint(lon=47.8915, lat=56.6317)
        b = GeoPoint(lon=47.8916, lat=56.6318)
        self.assertFalse(
            wikidata_poi_name_conflict(
                "Марийский национальный театр драмы",
                "Марийский театр оперы и балета",
            )
        )
        self.assertTrue(
            poi_name_conflict(
                "Марийский национальный театр драмы",
                a,
                "Марийский театр оперы и балета",
                b,
            )
        )
        self.assertFalse(
            poi_name_conflict(
                "Марийский национальный театр драмы",
                a,
                "Марийский театр оперы и балета",
                b,
                relaxed=True,
            )
        )

    def test_accepts_named_embankment_geo_member(self) -> None:
        from search.yandex.poi_filters import is_acceptable_geo_member

        member = {
            "GeoObject": {
                "name": "Волжская набережная",
                "Point": {"pos": "50.15 53.20"},
                "metaDataProperty": {
                    "GeocoderMetaData": {
                        "kind": "street",
                        "text": "Россия, Самарская область, Самара, Волжская набережная",
                    }
                },
            }
        }
        self.assertTrue(
            is_acceptable_geo_member(member, city_hint="Самара")
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

    def test_route_url_close_loop_repeats_start(self) -> None:
        start = GeoPoint(lon=40.92, lat=57.76)
        mid = GeoPoint(lon=40.93, lat=57.77)
        end = GeoPoint(lon=40.94, lat=57.75)
        url = build_maps_route_url(
            [start, mid, end],
            city="Кострома",
            close_loop=True,
        )
        decoded = unquote(url)
        parts = decoded.split("rtext=")[1].split("&")[0].split("~")
        self.assertEqual(len(parts), 4)
        self.assertEqual(parts[0], parts[-1])

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
