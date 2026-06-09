"""Тесты пост-обработки маршрутов."""

from __future__ import annotations

import unittest

from agents.route_postprocess import (
    build_fallback_route_program,
    estimate_path_km,
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
from search.yandex.poi_filters import route_name_key


def _kostroma_materials() -> RouteMaterials:
    """Координаты из city_landmarks + дубликат «Красные ряды»."""
    specs = [
        ("susan", "Сусанинская площадь", 40.927155, 57.768072),
        ("bogo", "Богоявленско-Анастасин монастырь", 40.9256, 57.7661),
        ("ipat", "Ипатьевский монастырь", 40.8782, 57.7781),
        ("kal", "Пожарная каланча", 40.9263, 57.7672),
        ("ryady", "Торговые ряды", 40.925538, 57.766684),
        ("nab", "Набережная Волги", 40.922088, 57.753649),
        ("dendro", "Костромской дендропарк", 40.972564, 57.820511),
        ("museum", "Музей деревянного зодчества", 40.9909, 57.8029),
    ]
    return RouteMaterials(
        city="Кострома",
        dates="июнь",
        provider="yandex_maps",
        leisure_points=[
            PoiPoint(
                poi_id=pid,
                tag="landmarks",
                name=name,
                coordinates=GeoPoint(lon=lon, lat=lat),
                maps_url=f"https://yandex.ru/maps/org/{pid}",
            )
            for pid, name, lon, lat in specs
        ],
        dining_options=[],
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

    def test_route_variants_grow_in_stops(self) -> None:
        materials = RouteMaterials(
            city="Москва",
            dates="июнь",
            provider="fallback",
            leisure_points=[
                PoiPoint(
                    poi_id=f"l{i}",
                    tag="landmarks",
                    name=f"POI {i}",
                    coordinates=GeoPoint(lon=37.60 + i * 0.008, lat=55.75 + (i % 2) * 0.004),
                    maps_url=f"https://yandex.ru/maps/org/l{i}",
                )
                for i in range(8)
            ],
            dining_options=[],
        )
        program = build_fallback_route_program(materials)
        counts = [
            len([s for s in case.stops if s.kind == "leisure"])
            for case in program.cases
        ]
        self.assertEqual(len(counts), 3)
        self.assertLessEqual(counts[0], counts[1])
        self.assertLessEqual(counts[1], counts[2])
        self.assertGreaterEqual(counts[0], 3)
        self.assertGreaterEqual(counts[1], 4)
        self.assertGreaterEqual(counts[2], 5)

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

    def test_kostroma_no_duplicate_names_and_min_distance(self) -> None:
        materials = _kostroma_materials()
        program = build_fallback_route_program(materials)
        for case in program.cases:
            leisure_stops = [s for s in case.stops if s.kind == "leisure"]
            names = [route_name_key(s.narrative) for s in leisure_stops]
            self.assertEqual(len(names), len(set(names)), case.case_id)
            coords = [
                materials.leisure_points[
                    next(i for i, p in enumerate(materials.leisure_points) if p.poi_id == s.poi_id)
                ].coordinates
                for s in leisure_stops
            ]
            km = estimate_path_km(coords)
            if case.case_id == "A":
                self.assertGreaterEqual(km, 2.0, case.case_id)
                self.assertLessEqual(km, 5.5, case.case_id)
            else:
                self.assertGreaterEqual(km, 3.0, case.case_id)

    def test_kostroma_long_route_has_more_stops(self) -> None:
        materials = _kostroma_materials()
        program = build_fallback_route_program(materials)
        counts = [
            len([s for s in case.stops if s.kind == "leisure"])
            for case in program.cases
        ]
        self.assertGreaterEqual(counts[2], 5)
        self.assertLess(counts[0], counts[2])

    def test_kostroma_routes_are_diverse(self) -> None:
        materials = _kostroma_materials()
        program = build_fallback_route_program(materials)
        a, b, c = program.cases
        self.assertLess(leisure_overlap_ratio(a, b), 0.75)
        self.assertLess(leisure_overlap_ratio(b, c), 0.7)

    def test_kostroma_uses_landmark_names(self) -> None:
        from search.yandex.poi_filters import is_generic_street_name

        materials = _kostroma_materials()
        program = build_fallback_route_program(materials)
        for case in program.cases:
            for stop in case.stops:
                if stop.kind != "leisure":
                    continue
                self.assertFalse(
                    is_generic_street_name(stop.narrative),
                    stop.narrative,
                )


if __name__ == "__main__":
    unittest.main()
