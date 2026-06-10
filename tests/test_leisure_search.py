"""Тесты поиска leisure через Overpass + discovery match."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from models.routes import GeoPoint, PoiPoint
from search.yandex.leisure_search import search_leisure_points


def _samara_center():
    from search.osm.nominatim import CityCenter

    return CityCenter(
        city="Самара",
        lon=50.15,
        lat=53.20,
        bbox=(49.95, 53.05, 50.35, 53.35),
        wikidata_id="Q894",
    )


def _sample_osm_poi(name: str, poi_id: str, lon: float, lat: float) -> PoiPoint:
    return PoiPoint(
        poi_id=poi_id,
        tag="landmarks",
        name=name,
        coordinates=GeoPoint(lon=lon, lat=lat),
        maps_url=f"https://yandex.ru/maps/?pt={lon},{lat}&z=16",
    )


class TestLeisureSearch(unittest.TestCase):
    @patch.dict("os.environ", {"POI_USE_OVERPASS": "true"}, clear=False)
    @patch("search.yandex.landmark_discovery.run_landmark_discovery")
    @patch("search.yandex.leisure_search.fetch_wikidata_leisure")
    @patch("search.yandex.leisure_search.fetch_overpass_leisure")
    @patch("search.yandex.leisure_search.resolve_city_center")
    def test_collects_osm_pool_with_discovery_boost(
        self,
        resolve_city_center,
        fetch_overpass,
        fetch_wikidata,
        run_landmark_discovery,
    ) -> None:
        from search.yandex.landmark_discovery import LandmarkDiscoveryTrace

        resolve_city_center.return_value = _samara_center()
        fetch_overpass.return_value = [
            _sample_osm_poi("Музей модерна", "osm_node_1", 50.11, 53.19),
            _sample_osm_poi("Стела «Ладья»", "osm_node_2", 50.12, 53.20),
            _sample_osm_poi("Самарская набережная", "osm_node_3", 50.13, 53.21),
        ]
        fetch_wikidata.return_value = []
        run_landmark_discovery.return_value = (
            ["Музей модерна", "Стела Ладья"],
            LandmarkDiscoveryTrace(
                provider="ddgs",
                landmark_names=["Музей модерна", "Стела Ладья"],
            ),
        )
        result = search_leisure_points(city="Самара", categories=["landmarks"], pace="relaxed")
        names = [p.name for p in result.points]
        self.assertGreaterEqual(len(names), 2)
        self.assertTrue(any("Музей" in n for n in names))
        self.assertIsNotNone(result.landmark_discovery)
        self.assertGreaterEqual(len(result.landmark_discovery.get("matched_pois") or []), 1)
        fetch_overpass.assert_called_once()
        fetch_wikidata.assert_called_once()
        run_landmark_discovery.assert_called_once_with("Самара")

    @patch("search.yandex.landmark_discovery.run_landmark_discovery")
    @patch("search.yandex.leisure_search.fetch_wikidata_leisure")
    @patch("search.yandex.leisure_search.fetch_overpass_leisure")
    @patch("search.yandex.leisure_search.resolve_city_center")
    def test_overpass_skipped_by_default(
        self,
        resolve_city_center,
        fetch_overpass,
        fetch_wikidata,
        run_landmark_discovery,
    ) -> None:
        from search.yandex.landmark_discovery import LandmarkDiscoveryTrace

        resolve_city_center.return_value = _samara_center()
        fetch_wikidata.return_value = [
            _sample_osm_poi("Музей", "Q123", 50.11, 53.19),
        ]
        run_landmark_discovery.return_value = (
            [],
            LandmarkDiscoveryTrace(provider="ddgs", landmark_names=[]),
        )
        result = search_leisure_points(city="Самара", categories=["landmarks"])
        self.assertGreaterEqual(len(result.points), 1)
        fetch_overpass.assert_not_called()

    @patch("search.yandex.leisure_search.fetch_nominatim_embankments")
    @patch("search.yandex.landmark_discovery.run_landmark_discovery")
    @patch("search.yandex.leisure_search.fetch_wikidata_leisure")
    @patch("search.yandex.leisure_search.fetch_overpass_leisure")
    @patch("search.yandex.leisure_search.resolve_city_center")
    def test_embankments_skipped_when_wikidata_enabled(
        self,
        resolve_city_center,
        fetch_overpass,
        fetch_wikidata,
        run_landmark_discovery,
        fetch_embankments,
    ) -> None:
        from search.yandex.landmark_discovery import LandmarkDiscoveryTrace

        resolve_city_center.return_value = _samara_center()
        fetch_wikidata.return_value = [_sample_osm_poi("Музей", "Q1", 50.13, 53.21)]
        fetch_overpass.return_value = []
        run_landmark_discovery.return_value = (
            [],
            LandmarkDiscoveryTrace(provider="ddgs", landmark_names=[]),
        )
        search_leisure_points(city="Самара", categories=["landmarks"])
        fetch_embankments.assert_not_called()

    @patch.dict("os.environ", {"POI_USE_WIKIDATA": "false"}, clear=False)
    @patch("search.yandex.leisure_search.fetch_nominatim_embankments")
    @patch("search.yandex.leisure_search.fetch_overpass_leisure")
    @patch("search.yandex.leisure_search.resolve_city_center")
    def test_embankments_from_nominatim_without_wikidata(
        self,
        resolve_city_center,
        fetch_overpass,
        fetch_embankments,
    ) -> None:
        resolve_city_center.return_value = _samara_center()
        fetch_overpass.return_value = []
        emb = _sample_osm_poi("Волжская набережная", "osm_way_9", 50.13, 53.21)
        fetch_embankments.return_value = [emb.model_copy(update={"tag": "embankments"})]
        result = search_leisure_points(city="Самара", categories=["landmarks"])
        fetch_embankments.assert_called_once_with("Самара", _samara_center(), max_items=4)
        self.assertTrue(any(p.tag == "embankments" for p in result.points))

    @patch("search.yandex.leisure_search.resolve_city_center", return_value=None)
    def test_demo_when_city_not_found(self, _resolve) -> None:
        result = search_leisure_points(city="Несуществующий", categories=["landmarks"])
        self.assertTrue(all("/org/demo_" in p.maps_url for p in result.points))


if __name__ == "__main__":
    unittest.main()
