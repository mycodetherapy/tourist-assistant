"""Тесты пост-обработки маршрутов."""

from __future__ import annotations

import unittest

from agents.route_postprocess import (
    build_fallback_route_program,
    format_routes_text,
    leisure_overlap_ratio,
)
from models.routes import (
    DiningOption,
    GeoPoint,
    PoiPoint,
    RouteMaterials,
    RouteStop,
    TripRouteCase,
)


class TestRoutePostprocess(unittest.TestCase):
    def test_build_fallback_three_cases_with_urls(self) -> None:
        materials = RouteMaterials(
            city="Москва",
            dates="октябрь",
            provider="fallback",
            leisure_points=[
                PoiPoint(
                    poi_id=f"l{i}",
                    tag="landmarks",
                    name=f"POI {i}",
                    coordinates=GeoPoint(lon=37.6 + i * 0.01, lat=55.75),
                    maps_url=f"https://yandex.ru/maps/org/l{i}",
                )
                for i in range(4)
            ],
            dining_options=[
                DiningOption(
                    poi_id="d0",
                    anchor_poi_id="l0",
                    name="Кафе",
                    coordinates=GeoPoint(lon=37.61, lat=55.751),
                    maps_url="https://yandex.ru/maps/org/d0",
                )
            ],
        )
        program = build_fallback_route_program(materials)
        self.assertEqual(len(program.cases), 3)
        for case in program.cases:
            self.assertTrue(case.maps_route_url.startswith("https://yandex.ru/maps/"))
        text = format_routes_text(program)
        self.assertIn("## Вариант A", text)

    def test_overlap_ratio_differs_for_distinct_cases(self) -> None:
        a = TripRouteCase(
            case_id="A",
            title="A",
            summary="",
            stops=[
                RouteStop(order=1, kind="leisure", poi_id="l1", narrative="1"),
                RouteStop(order=2, kind="leisure", poi_id="l2", narrative="2"),
            ],
        )
        b = TripRouteCase(
            case_id="B",
            title="B",
            summary="",
            stops=[
                RouteStop(order=1, kind="leisure", poi_id="l3", narrative="3"),
                RouteStop(order=2, kind="leisure", poi_id="l4", narrative="4"),
            ],
        )
        self.assertEqual(leisure_overlap_ratio(a, b), 0.0)


if __name__ == "__main__":
    unittest.main()
