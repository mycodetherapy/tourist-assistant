"""Тесты базовой точки в URL маршрута."""

from __future__ import annotations

import unittest

from models.routes import GeoPoint
from search.yandex.route_url import build_maps_route_url, parse_maps_route_points


class TestRouteAnchorUrl(unittest.TestCase):
    def test_anchor_prepended_not_in_max_stops(self) -> None:
        pois = [
            GeoPoint(lat=55.75 + i * 0.01, lon=37.62 + i * 0.01) for i in range(10)
        ]
        url = build_maps_route_url(
            pois,
            max_stops=8,
            anchor_lat=55.70,
            anchor_lon=37.60,
        )
        points = parse_maps_route_points(url)
        self.assertEqual(points[0].lat, 55.70)
        self.assertEqual(points[0].lon, 37.60)
        self.assertEqual(len(points), 9)

    def test_anchor_loop_end_closes_route(self) -> None:
        pois = [
            GeoPoint(lat=55.75, lon=37.62),
            GeoPoint(lat=55.76, lon=37.63),
        ]
        url = build_maps_route_url(
            pois,
            anchor_lat=55.70,
            anchor_lon=37.60,
            anchor_loop_end=True,
        )
        points = parse_maps_route_points(url)
        self.assertEqual(len(points), 4)
        self.assertAlmostEqual(points[0].lat, points[-1].lat, places=4)
        self.assertAlmostEqual(points[0].lon, points[-1].lon, places=4)


if __name__ == "__main__":
    unittest.main()
