"""Тесты OSRM-клиента (без реального сервера)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from models.routes import GeoPoint
from search.osrm.client import fetch_foot_route, resolve_osrm_base_url


class TestOsrmClient(unittest.TestCase):
    def test_returns_none_without_base_url(self) -> None:
        points = [GeoPoint(lat=55.79, lon=49.12), GeoPoint(lat=55.80, lon=49.13)]
        with patch.dict("os.environ", {"OSRM_BASE_URL": "", "OSRM_URL_BY_SLUG": ""}, clear=False):
            self.assertIsNone(fetch_foot_route(points))

    def test_returns_none_for_single_point(self) -> None:
        self.assertIsNone(
            fetch_foot_route([GeoPoint(lat=55.79, lon=49.12)], base_url="http://osrm:5000")
        )

    def test_parses_geojson_route(self) -> None:
        payload = {
            "code": "Ok",
            "routes": [
                {
                    "distance": 1200.5,
                    "duration": 900.0,
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[49.12, 55.79], [49.125, 55.795], [49.13, 55.80]],
                    },
                }
            ],
        }
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = payload

        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = False
        mock_client.get.return_value = mock_response

        points = [GeoPoint(lat=55.79, lon=49.12), GeoPoint(lat=55.80, lon=49.13)]
        with patch("search.osrm.client.httpx.Client", return_value=mock_client):
            result = fetch_foot_route(points, base_url="http://osrm:5000")

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.distance_m, 1200.5)
        self.assertEqual(result.duration_s, 900.0)
        self.assertEqual(len(result.geometry.coordinates), 3)
        self.assertEqual(result.geometry.coordinates[0], [49.12, 55.79])

    def test_resolve_skips_other_city_when_dataset_set(self) -> None:
        env = {
            "OSRM_BASE_URL": "http://osrm:5000",
            "OSRM_DATASET": "kazan",
            "OSRM_URL_BY_SLUG": "",
        }
        with patch.dict("os.environ", env, clear=False):
            self.assertEqual(resolve_osrm_base_url("Казань"), "http://osrm:5000")
            self.assertIsNone(resolve_osrm_base_url("Самара"))

    def test_resolve_url_by_slug(self) -> None:
        env = {
            "OSRM_BASE_URL": "http://osrm:5000",
            "OSRM_DATASET": "kazan",
            "OSRM_URL_BY_SLUG": "samara=http://osrm-samara:5000,kazan=http://osrm:5000",
        }
        with patch.dict("os.environ", env, clear=False):
            self.assertEqual(resolve_osrm_base_url("Самара"), "http://osrm-samara:5000")
            self.assertEqual(resolve_osrm_base_url("Казань"), "http://osrm:5000")


if __name__ == "__main__":
    unittest.main()
