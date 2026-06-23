"""Тесты клиента OSRM."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from models.routes import GeoPoint
from search.osm.routing import fetch_walk_route


class TestOsmRouting(unittest.TestCase):
    @patch("search.osm.routing.is_osrm_enabled", return_value=False)
    def test_disabled_returns_none(self, _enabled: MagicMock) -> None:
        points = [GeoPoint(lon=49.12, lat=55.79), GeoPoint(lon=49.13, lat=55.80)]
        self.assertIsNone(fetch_walk_route(points))

    @patch("search.osm.routing.requests.get")
    @patch("search.osm.routing.is_osrm_enabled", return_value=True)
    @patch("search.osm.routing.get_osrm_url", return_value="http://127.0.0.1:5000")
    def test_parses_geojson_line(
        self,
        _url: MagicMock,
        _enabled: MagicMock,
        mock_get: MagicMock,
    ) -> None:
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
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
            },
        )
        points = [GeoPoint(lon=49.12, lat=55.79), GeoPoint(lon=49.13, lat=55.80)]
        result = fetch_walk_route(points)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.geometry.type, "LineString")
        self.assertEqual(len(result.geometry.coordinates), 3)
        self.assertAlmostEqual(result.distance_m, 1200.5)
        self.assertAlmostEqual(result.duration_s, 900.0)
        called_url = mock_get.call_args[0][0]
        self.assertIn("/route/v1/foot/", called_url)
        self.assertIn("49.12,55.79", called_url)

    @patch("search.osm.routing.requests.get")
    @patch("search.osm.routing.is_osrm_enabled", return_value=True)
    @patch("search.osm.routing.get_osrm_url", return_value="http://127.0.0.1:5000")
    def test_osrm_error_returns_none(
        self,
        _url: MagicMock,
        _enabled: MagicMock,
        mock_get: MagicMock,
    ) -> None:
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"code": "NoRoute", "message": "No route found"},
        )
        points = [GeoPoint(lon=1.0, lat=2.0), GeoPoint(lon=3.0, lat=4.0)]
        self.assertIsNone(fetch_walk_route(points))


if __name__ == "__main__":
    unittest.main()
