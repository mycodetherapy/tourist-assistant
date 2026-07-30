"""Тесты политики Wikidata vs city pack."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from models.routes import GeoPoint, PoiPoint
from search.osm.nominatim import CityCenter
from search.yandex.leisure_search import search_leisure_points


class LeisureSearchPolicyTests(unittest.TestCase):
    @patch("search.yandex.leisure_search.fetch_wikidata_leisure")
    @patch("search.yandex.leisure_search.fetch_city_pack_poi")
    @patch("search.yandex.leisure_search.is_pack_ready", return_value=False)
    @patch("search.yandex.leisure_search.ensure_pack_async")
    @patch("search.yandex.leisure_search.resolve_city_center")
    def test_catalog_city_uses_wikidata_when_pack_missing(
        self,
        mock_center,
        mock_ensure,
        _mock_ready,
        mock_pack_poi,
        mock_wikidata,
    ) -> None:
        mock_center.return_value = CityCenter(
            city="Казань",
            lon=49.12,
            lat=55.79,
            bbox=(48.9, 55.6, 49.3, 56.0),
            wikidata_id="Q4240",
            display_name="Казань",
        )
        mock_pack_poi.return_value = []
        mock_wikidata.return_value = [
            PoiPoint(
                poi_id="Q1",
                tag="landmarks",
                name="Кремль",
                coordinates=GeoPoint(lon=49.12, lat=55.79),
                maps_url="https://yandex.ru/maps",
            )
        ]
        result = search_leisure_points(city="Казань", categories=[])
        mock_ensure.assert_called_once()
        mock_wikidata.assert_called_once()
        mock_pack_poi.assert_not_called()
        self.assertEqual(result.pack_status, "building")
        self.assertTrue(result.points)
        self.assertNotIn("/org/demo_", result.points[0].maps_url)

    @patch("search.yandex.leisure_search.fetch_wikidata_leisure")
    @patch("search.yandex.leisure_search.fetch_city_pack_poi")
    @patch("search.yandex.leisure_search.is_pack_ready", return_value=True)
    @patch("search.yandex.leisure_search.resolve_city_center")
    def test_ready_pack_uses_sqlite(
        self,
        mock_center,
        _mock_ready,
        mock_pack_poi,
        mock_wikidata,
    ) -> None:
        mock_center.return_value = CityCenter(
            city="Казань",
            lon=49.12,
            lat=55.79,
            bbox=(48.9, 55.6, 49.3, 56.0),
            wikidata_id="Q4240",
            display_name="Казань",
        )
        poi = PoiPoint(
            poi_id="osm_1",
            tag="landmarks",
            name="Тест",
            coordinates=GeoPoint(lon=49.12, lat=55.79),
            maps_url="https://yandex.ru/maps",
        )
        mock_pack_poi.return_value = [poi]
        result = search_leisure_points(city="Казань", categories=[])
        mock_wikidata.assert_not_called()
        mock_pack_poi.assert_called_once()
        self.assertEqual(result.pack_status, "ready")
        self.assertTrue(result.points)

    @patch("search.yandex.leisure_search.fetch_wikidata_leisure")
    @patch("search.yandex.leisure_search.fetch_city_pack_poi", return_value=[])
    @patch("search.yandex.leisure_search.is_pack_ready", return_value=True)
    @patch("search.yandex.leisure_search.resolve_city_center")
    def test_ready_pack_empty_falls_back_to_wikidata(
        self,
        mock_center,
        _mock_ready,
        mock_pack_poi,
        mock_wikidata,
    ) -> None:
        mock_center.return_value = CityCenter(
            city="Казань",
            lon=49.12,
            lat=55.79,
            bbox=(48.9, 55.6, 49.3, 56.0),
            wikidata_id="Q4240",
            display_name="Казань",
        )
        mock_wikidata.return_value = [
            PoiPoint(
                poi_id="Q2",
                tag="museums",
                name="Музей",
                coordinates=GeoPoint(lon=49.11, lat=55.78),
                maps_url="https://yandex.ru/maps",
            )
        ]
        result = search_leisure_points(city="Казань", categories=[])
        mock_pack_poi.assert_called_once()
        mock_wikidata.assert_called_once()
        self.assertEqual(result.pack_status, "ready")
        self.assertEqual(result.points[0].poi_id, "Q2")

    @patch("search.yandex.leisure_search.fetch_wikidata_leisure", return_value=[])
    @patch("search.yandex.leisure_search.resolve_city_center")
    def test_outside_catalog_uses_wikidata(
        self,
        mock_center,
        mock_wikidata,
    ) -> None:
        mock_center.return_value = CityCenter(
            city="ГородВнеКаталога",
            lon=37.62,
            lat=55.75,
            bbox=(37.4, 55.6, 37.8, 55.9),
            wikidata_id="",
            display_name="ГородВнеКаталога",
        )
        search_leisure_points(city="ГородВнеКаталога", categories=[])
        mock_wikidata.assert_called_once()


if __name__ == "__main__":
    unittest.main()
