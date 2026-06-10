"""Тесты пост-обработки маршрутов."""

from __future__ import annotations

import unittest

from agents.route_postprocess import (
    _resolve_route_loop,
    build_fallback_route_program,
    build_hybrid_route_program,
    enforce_route_poi_policy,
    estimate_path_km,
    finalize_route_program,
    format_routes_text,
    leisure_overlap_ratio,
    public_route_summary,
    public_route_title,
)
from search.yandex.route_url import parse_maps_route_points
from models.routes import (
    DiningOption,
    GeoPoint,
    PoiPoint,
    RouteMaterials,
    RouteProgram,
    RouteStop,
    TripRouteCase,
)
from search.yandex.poi_filters import route_name_key


def _kostroma_materials() -> RouteMaterials:
    """Тестовый пул POI Костромы (координаты для регрессии маршрутов)."""
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
    def test_public_route_title_strips_parens(self) -> None:
        self.assertEqual(public_route_title("Лёгкая прогулка (~4 км)"), "Лёгкая прогулка")

    def test_estimate_path_km_close_loop_includes_return(self) -> None:
        coords = [
            GeoPoint(lon=40.927155, lat=57.768072),
            GeoPoint(lon=40.9263, lat=57.7672),
            GeoPoint(lon=40.925538, lat=57.766684),
        ]
        linear = estimate_path_km(coords)
        loop = estimate_path_km(coords, close_loop=True)
        self.assertGreater(loop, linear)

    def test_loop_route_llm_flag_closes_maps_url(self) -> None:
        materials = _kostroma_materials()
        draft = RouteProgram(
            cases=[
                TripRouteCase(
                    case_id="A",
                    title="A",
                    summary="",
                    loop_route=True,
                    stops=[
                        RouteStop(order=1, kind="leisure", poi_id="susan", narrative=""),
                        RouteStop(order=2, kind="leisure", poi_id="kal", narrative=""),
                        RouteStop(order=3, kind="leisure", poi_id="ryady", narrative=""),
                    ],
                ),
                TripRouteCase(case_id="B", title="B", summary="", stops=[]),
                TripRouteCase(case_id="C", title="C", summary="", stops=[]),
            ]
        )
        program = finalize_route_program(draft, materials)
        case_a = program.cases[0]
        self.assertTrue(case_a.loop_route)
        self.assertIn("Кольцевая", case_a.summary)
        points = parse_maps_route_points(case_a.maps_route_url)
        self.assertGreaterEqual(len(points), 4)
        self.assertEqual(points[0].lat, points[-1].lat)
        self.assertEqual(points[0].lon, points[-1].lon)

    def test_bridges_and_embankment_heuristic_suggests_loop(self) -> None:
        from agents.route_postprocess import _adapt_profiles, _landmark_pool, _pool_span_km

        materials = RouteMaterials(
            city="Тестград",
            dates="июнь",
            provider="fallback",
            leisure_points=[
                PoiPoint(
                    poi_id="bridge_a",
                    tag="landmarks",
                    name="Железнодорожный мост",
                    coordinates=GeoPoint(lon=50.10, lat=53.20),
                    maps_url="https://yandex.ru/maps/org/bridge_a",
                ),
                PoiPoint(
                    poi_id="bridge_b",
                    tag="landmarks",
                    name="Пешеходный мост",
                    coordinates=GeoPoint(lon=50.11, lat=53.21),
                    maps_url="https://yandex.ru/maps/org/bridge_b",
                ),
                PoiPoint(
                    poi_id="nab",
                    tag="embankments",
                    name="Волжская набережная",
                    coordinates=GeoPoint(lon=50.105, lat=53.205),
                    maps_url="https://yandex.ru/maps/org/nab",
                ),
                PoiPoint(
                    poi_id="sq",
                    tag="landmarks",
                    name="Центральная площадь",
                    coordinates=GeoPoint(lon=50.108, lat=53.208),
                    maps_url="https://yandex.ru/maps/org/sq",
                ),
            ],
            dining_options=[],
        )
        pool = _landmark_pool(materials.leisure_points)
        indices = list(range(len(pool)))
        span_km = _pool_span_km(pool)
        profile = _adapt_profiles(pool)["A"]
        case = TripRouteCase(case_id="A", title="A", summary="", stops=[])
        close_loop, _ = _resolve_route_loop(
            case,
            pool,
            indices,
            span_km,
            profile,
            compact=True,
            max_km=5.0,
            city_hint="Тестград",
        )
        self.assertTrue(close_loop)

    def test_public_route_summary_strips_km(self) -> None:
        raw = "Пешая прогулка по Кострома: лёгкая прогулка (~4 км), ~2.5 км, 5 остановок."
        cleaned = public_route_summary(raw)
        self.assertNotIn("км", cleaned.lower())
        self.assertIn("5 остановок", cleaned)

    def test_hybrid_empty_pool_no_crash(self) -> None:
        materials = RouteMaterials(city="Кострома", dates="июнь", leisure_points=[])
        draft = RouteProgram(cases=[])
        program = build_hybrid_route_program(materials, draft)
        self.assertEqual(len(program.cases), 3)

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

    def test_route_variants_grow_in_km(self) -> None:
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
                for i in range(12)
            ],
            dining_options=[],
        )
        program = build_fallback_route_program(materials)

        def _km(case: TripRouteCase) -> float:
            coords = [
                next(p.coordinates for p in materials.leisure_points if p.poi_id == s.poi_id)
                for s in case.stops
                if s.kind == "leisure" and s.poi_id
            ]
            return estimate_path_km(coords)

        kms = [_km(case) for case in program.cases]
        self.assertEqual(len(kms), 3)
        self.assertLess(kms[0], kms[1])
        self.assertLess(kms[1], kms[2])
        for case in program.cases:
            leisure_n = len([s for s in case.stops if s.kind == "leisure"])
            self.assertGreaterEqual(leisure_n, 3)

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
                self.assertGreaterEqual(km, 1.5, case.case_id)
                self.assertLessEqual(km, 4.5, case.case_id)
            else:
                self.assertGreaterEqual(km, 3.0, case.case_id)

    def test_kostroma_long_route_has_more_km(self) -> None:
        materials = _kostroma_materials()
        program = build_fallback_route_program(materials)

        def _km(case: TripRouteCase) -> float:
            coords = [
                materials.leisure_points[
                    next(i for i, p in enumerate(materials.leisure_points) if p.poi_id == s.poi_id)
                ].coordinates
                for s in case.stops
                if s.kind == "leisure" and s.poi_id
            ]
            return estimate_path_km(coords)

        kms = [_km(c) for c in program.cases]
        self.assertGreater(kms[2], kms[0])

    def test_finalize_separates_identical_llm_drafts(self) -> None:
        materials = _kostroma_materials()
        poi_ids = ["susan", "kal", "ryady", "bogo", "nab"]
        same_stops = [
            RouteStop(order=i + 1, kind="leisure", poi_id=pid, narrative="")
            for i, pid in enumerate(poi_ids)
        ]
        draft = RouteProgram(
            cases=[
                TripRouteCase(case_id="A", title="A", summary="", stops=same_stops),
                TripRouteCase(case_id="B", title="B", summary="", stops=same_stops),
                TripRouteCase(case_id="C", title="C", summary="", stops=same_stops),
            ]
        )
        program = finalize_route_program(draft, materials)
        a, b, c = program.cases
        self.assertLess(leisure_overlap_ratio(a, b), 0.85)
        self.assertLess(leisure_overlap_ratio(b, c), 0.85)

    def test_kostroma_routes_are_diverse(self) -> None:
        materials = _kostroma_materials()
        program = build_fallback_route_program(materials)
        a, b, c = program.cases
        self.assertLess(leisure_overlap_ratio(a, b), 0.75)
        self.assertLess(leisure_overlap_ratio(b, c), 0.7)

    def test_hybrid_keeps_llm_ranking_for_valid_case_a(self) -> None:
        materials = _kostroma_materials()
        fallback = build_fallback_route_program(materials)

        def _poi_ids(case: TripRouteCase) -> list[str]:
            return [s.poi_id for s in case.stops if s.kind == "leisure" and s.poi_id]

        draft = RouteProgram(
            cases=[
                TripRouteCase(
                    case_id="A",
                    title="A",
                    summary="",
                    stops=[
                        RouteStop(order=1, kind="leisure", poi_id="susan", narrative=""),
                        RouteStop(order=2, kind="leisure", poi_id="kal", narrative=""),
                        RouteStop(order=3, kind="leisure", poi_id="ryady", narrative=""),
                        RouteStop(order=4, kind="leisure", poi_id="bogo", narrative=""),
                    ],
                ),
                TripRouteCase(
                    case_id="B",
                    title="B",
                    summary="",
                    stops=[
                        RouteStop(order=i, kind="leisure", poi_id=pid, narrative="")
                        for i, pid in enumerate(_poi_ids(fallback.cases[1]), start=1)
                    ],
                ),
                TripRouteCase(
                    case_id="C",
                    title="C",
                    summary="",
                    stops=[
                        RouteStop(order=i, kind="leisure", poi_id=pid, narrative="")
                        for i, pid in enumerate(_poi_ids(fallback.cases[2]), start=1)
                    ],
                ),
            ]
        )
        hybrid = build_hybrid_route_program(materials, draft)
        a_stops = [s for s in hybrid.cases[0].stops if s.kind == "leisure"]
        a_ids = [s.poi_id for s in a_stops if s.poi_id]
        self.assertGreaterEqual(len(a_ids), 3)
        self.assertTrue({"susan", "kal", "ryady", "bogo"}.issubset(set(a_ids)))
        a_coords = [
            next(p.coordinates for p in materials.leisure_points if p.poi_id == s.poi_id)
            for s in a_stops
            if s.poi_id
        ]
        self.assertGreaterEqual(estimate_path_km(a_coords), 1.5)
        self.assertLessEqual(estimate_path_km(a_coords), 4.5)

    def test_hybrid_falls_back_when_llm_poi_invalid(self) -> None:
        materials = _kostroma_materials()
        fallback = build_fallback_route_program(materials)

        def _poi_ids(case: TripRouteCase) -> list[str]:
            return [s.poi_id for s in case.stops if s.kind == "leisure" and s.poi_id]

        draft = RouteProgram(
            cases=[
                TripRouteCase(
                    case_id="A",
                    title="A",
                    summary="",
                    stops=[
                        RouteStop(order=1, kind="leisure", poi_id="unknown", narrative=""),
                    ],
                ),
                TripRouteCase(
                    case_id="B",
                    title="B",
                    summary="",
                    stops=[
                        RouteStop(order=i, kind="leisure", poi_id=pid, narrative="")
                        for i, pid in enumerate(_poi_ids(fallback.cases[1]), start=1)
                    ],
                ),
                TripRouteCase(
                    case_id="C",
                    title="C",
                    summary="",
                    stops=[
                        RouteStop(order=i, kind="leisure", poi_id=pid, narrative="")
                        for i, pid in enumerate(_poi_ids(fallback.cases[2]), start=1)
                    ],
                ),
            ]
        )
        hybrid = build_hybrid_route_program(materials, draft)
        self.assertEqual(
            set(_poi_ids(hybrid.cases[0])),
            set(_poi_ids(fallback.cases[0])),
        )

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


    def test_enforce_route_poi_policy_removes_banned(self) -> None:
        materials = _kostroma_materials()
        banned_id = materials.leisure_points[0].poi_id
        program = RouteProgram(
            cases=[
                TripRouteCase(
                    case_id="A",
                    title="A",
                    summary="s",
                    stops=[
                        RouteStop(
                            order=1,
                            kind="leisure",
                            poi_id=banned_id,
                            narrative=materials.leisure_points[0].name,
                        )
                    ],
                ),
                TripRouteCase(
                    case_id="B",
                    title="B",
                    summary="s",
                    stops=[
                        RouteStop(
                            order=1,
                            kind="leisure",
                            poi_id=materials.leisure_points[1].poi_id,
                            narrative=materials.leisure_points[1].name,
                        )
                    ],
                ),
                TripRouteCase(
                    case_id="C",
                    title="C",
                    summary="s",
                    stops=[
                        RouteStop(
                            order=1,
                            kind="leisure",
                            poi_id=materials.leisure_points[2].poi_id,
                            narrative=materials.leisure_points[2].name,
                        )
                    ],
                ),
            ]
        )
        fixed = enforce_route_poi_policy(
            program,
            materials,
            banned_poi_ids={banned_id},
            prefer_poi_ids=set(),
        )
        for case in fixed.cases:
            stop_ids = {s.poi_id for s in case.stops if s.kind == "leisure"}
            self.assertNotIn(banned_id, stop_ids)

        materials = _kostroma_materials()
        relaxed = build_fallback_route_program(materials, pace="relaxed")
        packed = build_fallback_route_program(materials, pace="packed")

        def _max_km(prog: RouteProgram) -> float:
            best = 0.0
            for case in prog.cases:
                coords = [
                    next(p.coordinates for p in materials.leisure_points if p.poi_id == s.poi_id)
                    for s in case.stops
                    if s.kind == "leisure" and s.poi_id
                ]
                best = max(best, estimate_path_km(coords))
            return best

        self.assertLessEqual(_max_km(relaxed), _max_km(packed))
        self.assertLess(
            leisure_overlap_ratio(relaxed.cases[0], relaxed.cases[2]),
            1.0,
        )


if __name__ == "__main__":
    unittest.main()
