"""Тесты базовой точки в URL маршрута."""

from __future__ import annotations

import unittest

from models.routes import GeoPoint
from search.yandex.route_url import (
    build_maps_route_open_url,
    build_maps_route_url,
    compute_route_map_markers,
    parse_maps_route_points,
)


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

    def test_compute_route_map_markers_with_anchor(self) -> None:
        pois = [
            GeoPoint(lat=55.75, lon=37.62),
            GeoPoint(lat=55.76, lon=37.63),
        ]
        anchor, leisure = compute_route_map_markers(
            pois,
            anchor_lat=55.70,
            anchor_lon=37.60,
        )
        self.assertIsNotNone(anchor)
        assert anchor is not None
        self.assertEqual(anchor.lat, 55.70)
        self.assertEqual(len(leisure), 2)

    def test_compute_route_map_markers_keeps_all_stops(self) -> None:
        """Метки на карте — по одной на каждую остановку, без дедупа."""
        near = GeoPoint(lat=56.6320, lon=47.8900)
        far = GeoPoint(lat=56.6400, lon=47.9000)
        pois = [near, near, far, GeoPoint(lat=56.6450, lon=47.9050)]
        anchor, leisure = compute_route_map_markers(
            pois,
            anchor_lat=56.6310,
            anchor_lon=47.8890,
        )
        self.assertIsNotNone(anchor)
        self.assertEqual(len(leisure), 4)

    def test_build_maps_route_open_url_uses_mapframe(self) -> None:
        url = build_maps_route_url(
            [GeoPoint(lat=55.75, lon=37.62), GeoPoint(lat=55.76, lon=37.63)],
        )
        open_url = build_maps_route_open_url(url)
        self.assertIn("yandex.ru/maps/", open_url)
        self.assertIn("from=mapframe", open_url)
        self.assertIn("source=mapframe", open_url)
        self.assertIn("mode=routes", open_url)
        self.assertIn("rtext=55.75%2C37.62~55.76%2C37.63", open_url)
        self.assertIn("rtt=pd", open_url)
        self.assertIn("ruri=~", open_url)

    def test_build_maps_route_url_kazan_path(self) -> None:
        url = build_maps_route_url(
            [GeoPoint(lat=55.79, lon=49.11), GeoPoint(lat=55.80, lon=49.12)],
            city="Казань",
        )
        self.assertIn("/maps/43/kazan/", url)
        self.assertIn("from=mapframe", url)


if __name__ == "__main__":
    unittest.main()
