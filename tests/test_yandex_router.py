"""Тесты Yandex Router API (пешая маршрутизация)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from models.routes import GeoPoint
from search.yandex.router import (
    _parse_route_response,
    fetch_walk_route,
    fetch_walk_route_for_maps_url,
    reference_points_for_router,
)


class TestYandexRouter(unittest.TestCase):
    def test_reference_points_drops_close_loop_duplicate(self) -> None:
        maps_url = (
            "https://yandex.ru/maps/?rtext="
            "55.800000,49.100000~55.810000,49.110000~55.800001,49.100001"
            "&rtt=pd"
        )
        points = reference_points_for_router(maps_url)
        self.assertEqual(len(points), 2)
        self.assertAlmostEqual(points[0].lat, 55.8, places=5)
        self.assertAlmostEqual(points[-1].lat, 55.81, places=5)

    def test_parse_route_response_builds_geojson(self) -> None:
        payload = {
            "route": {
                "legs": [
                    {
                        "status": "OK",
                        "steps": [
                            {
                                "length": 120.5,
                                "duration": 90.0,
                                "polyline": {
                                    "points": [[55.8, 49.1], [55.81, 49.11], [55.82, 49.12]],
                                },
                            }
                        ],
                    }
                ]
            }
        }
        result = _parse_route_response(payload)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.geometry.coordinates[0], [49.1, 55.8])
        self.assertEqual(result.geometry.coordinates[-1], [49.12, 55.82])
        self.assertAlmostEqual(result.distance_m, 120.5)
        self.assertAlmostEqual(result.duration_s, 90.0)

    @patch("search.yandex.router.get_api_key", return_value="test-key")
    @patch("search.yandex.router.requests.get")
    def test_fetch_walk_route_http_ok(self, mock_get: MagicMock, _key: MagicMock) -> None:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "route": {
                "legs": [
                    {
                        "status": "OK",
                        "steps": [
                            {
                                "length": 50,
                                "duration": 40,
                                "polyline": {"points": [[55.8, 49.1], [55.81, 49.11]]},
                            }
                        ],
                    }
                ]
            }
        }
        points = [
            GeoPoint(lat=55.8, lon=49.1),
            GeoPoint(lat=55.81, lon=49.11),
        ]
        result = fetch_walk_route(points)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(len(result.geometry.coordinates), 2)
        mock_get.assert_called_once()
        params = mock_get.call_args.kwargs["params"]
        self.assertEqual(params["mode"], "walking")
        self.assertEqual(params["waypoints"], "55.8,49.1|55.81,49.11")

    @patch("search.yandex.router.fetch_walk_route")
    def test_fetch_walk_route_for_maps_url(self, mock_fetch: MagicMock) -> None:
        maps_url = (
            "https://yandex.ru/maps/?rtext=55.800000,49.100000~55.810000,49.110000&rtt=pd"
        )
        mock_fetch.return_value = None
        self.assertIsNone(fetch_walk_route_for_maps_url(maps_url))
        called_points = mock_fetch.call_args.args[0]
        self.assertEqual(len(called_points), 2)


if __name__ == "__main__":
    unittest.main()
