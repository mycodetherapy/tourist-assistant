"""Тесты поиска leisure: city pack + Wikidata fallback."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from models.routes import GeoPoint, PoiPoint
from search.yandex.leisure_search import search_leisure_points


def _kazan_center():
    from search.osm.nominatim import CityCenter

    return CityCenter(
        city="Казань",
        lon=49.12,
        lat=55.79,
        bbox=(48.9, 55.6, 49.3, 56.0),
        wikidata_id="Q4247",
    )


def _sample_poi(name: str, poi_id: str, lon: float, lat: float) -> PoiPoint:
    return PoiPoint(
        poi_id=poi_id,
        tag="landmarks",
        name=name,
        coordinates=GeoPoint(lon=lon, lat=lat),
        maps_url=f"https://yandex.ru/maps/?pt={lon},{lat}&z=16",
    )


class TestLeisureSearch(unittest.TestCase):
    @patch("search.yandex.landmark_discovery.run_landmark_discovery")
    @patch("search.yandex.leisure_search.fetch_wikidata_leisure")
    @patch("search.yandex.leisure_search.fetch_city_pack_poi")
    @patch("search.yandex.leisure_search.is_pack_ready", return_value=True)
    @patch("search.yandex.leisure_search.resolve_city_slug", return_value="kazan")
    @patch("search.yandex.leisure_search.resolve_city_center")
    def test_uses_city_pack_when_ready(
        self,
        resolve_city_center,
        _resolve_slug,
        _pack_ready,
        fetch_city_pack,
        fetch_wikidata,
        run_landmark_discovery,
    ) -> None:
        from search.yandex.landmark_discovery import LandmarkDiscoveryTrace

        center = _kazan_center()
        resolve_city_center.return_value = center
        fetch_city_pack.return_value = [
            _sample_poi("Кремль", "osm_node_1", 49.10, 55.80),
        ]
        run_landmark_discovery.return_value = (
            [],
            LandmarkDiscoveryTrace(provider="ddgs", landmark_names=[]),
        )
        result = search_leisure_points(city="Казань", categories=["landmarks"])
        self.assertGreaterEqual(len(result.points), 1)
        fetch_city_pack.assert_called_once()
        fetch_wikidata.assert_not_called()

    @patch("search.yandex.leisure_search.ensure_pack_async")
    @patch("search.yandex.leisure_search.fetch_wikidata_leisure")
    @patch("search.yandex.leisure_search.fetch_city_pack_poi")
    @patch("search.yandex.leisure_search.is_pack_ready", return_value=False)
    @patch("search.yandex.leisure_search.resolve_city_slug", return_value="kazan")
    @patch("search.yandex.leisure_search.resolve_city_center")
    def test_wikidata_when_pack_missing(
        self,
        resolve_city_center,
        _resolve_slug,
        _pack_ready,
        fetch_city_pack,
        fetch_wikidata,
        ensure_pack_async,
    ) -> None:
        resolve_city_center.return_value = _kazan_center()
        fetch_wikidata.return_value = [_sample_poi("Музей", "Q1", 49.11, 55.79)]
        result = search_leisure_points(city="Казань", categories=["landmarks"])
        self.assertGreaterEqual(len(result.points), 1)
        fetch_city_pack.assert_not_called()
        fetch_wikidata.assert_called_once()
        ensure_pack_async.assert_called_once_with("Казань")

    @patch("search.yandex.leisure_search.resolve_city_center", return_value=None)
    def test_demo_when_city_not_found(self, _resolve) -> None:
        result = search_leisure_points(city="Несуществующий", categories=["landmarks"])
        self.assertTrue(all("/org/demo_" in p.maps_url for p in result.points))


if __name__ == "__main__":
    unittest.main()
