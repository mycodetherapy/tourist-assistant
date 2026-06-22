"""Регрессия: дизлайк остановки не должен «сгорать» и снова попадать в маршруты.

Сценарий из Саранска: 👎 на Собор Ушакова → пересборка убирает собор →
дизлайк удалялся как «устаревший» → при следующей пересборке собор возвращался.
"""

from __future__ import annotations

import json
import os
import unittest

from langchain_core.messages import ToolMessage

from agents.finalize_helpers import resolve_routes_program
from db.repository import (
    create_trip,
    get_latest_itinerary,
    list_item_feedback_by_section,
    save_itinerary_version,
    save_section_artifact,
    upsert_item_feedback,
)
from models.routes import GeoPoint, PoiPoint, RouteMaterials
from program.item_key import make_item_key, make_route_stop_key
from program.route_feedback import rebuild_poi_preferences, snapshot_route_feedback
from search.route_materials_store import ROUTE_MATERIALS_SECTION
from services.trip_service import TripService
from tests.db_test_helpers import skip_unless_pg, truncate_pg_tables
from tests.test_item_feedback import _sample_routes_program

CATHEDRAL_POI_ID = "Q2328333"
MONUMENT_POI_ID = "Q55655347"


def _saransk_materials() -> RouteMaterials:
    base = [
        (CATHEDRAL_POI_ID, "temples", "Собор Святого Феодора Ушакова", 45.18, 54.18),
        (MONUMENT_POI_ID, "monuments", "Памятник Ушакову (Саранск)", 45.19, 54.19),
        ("p1", "museums", "Национальный музей", 45.20, 54.20),
        ("p2", "landmarks", "Площадь Октябрьской Революции", 45.21, 54.21),
        ("p3", "parks", "Парк Победы", 45.22, 54.22),
        ("p4", "landmarks", "Музей изобразительных искусств", 45.23, 54.23),
        ("p5", "embankments", "Набережная реки Инсар", 45.24, 54.24),
        ("p6", "monuments", "Памятник Пушкину", 45.25, 54.25),
        ("p7", "theaters", "Мордовский театр оперы и балета", 45.26, 54.26),
        ("p8", "landmarks", "Свято-Троицкий собор", 45.27, 54.27),
    ]
    return RouteMaterials(
        city="Саранск",
        dates="июль",
        provider="fallback",
        leisure_points=[
            PoiPoint(
                poi_id=pid,
                tag=tag,
                name=name,
                coordinates=GeoPoint(lon=lon, lat=lat),
                maps_url=f"https://example.com/{pid}",
            )
            for pid, tag, name, lon, lat in base
        ],
        dining_options=[],
    )


def _tool_messages(materials: RouteMaterials) -> list[ToolMessage]:
    payload = {
        "materials": materials.model_dump(),
        "materials_digest": ", ".join(p.name for p in materials.leisure_points[:5]),
        "leisure_count": len(materials.leisure_points),
    }
    return [
        ToolMessage(
            content=json.dumps(payload, ensure_ascii=False),
            tool_call_id="m",
            name="search_route_materials",
        )
    ]


@skip_unless_pg
class TestRouteDislikeRegression(unittest.TestCase):
    def setUp(self) -> None:
        truncate_pg_tables()
        self.trip_id = create_trip("Саранск", "июль", "Москва", "тест")
        self.materials = _saransk_materials()
        save_section_artifact(
            self.trip_id,
            ROUTE_MATERIALS_SECTION,
            {"schema_version": 1, "materials": self.materials.model_dump()},
            digest="Саранск POI",
        )
        program = _sample_routes_program(["A", "B", "C"])
        save_itinerary_version(self.trip_id, program, scope="full")
        self.service = TripService()
        self.messages = _tool_messages(self.materials)

    def _all_route_poi_ids(self, program: dict) -> set[str]:
        from program.route_stops import collect_route_stop_poi_ids

        return set(collect_route_stop_poi_ids(program))

    def test_double_rebuild_keeps_ban_after_poi_removed_from_routes(self) -> None:
        """Главная регрессия: второй rebuild всё ещё без дизлайкнутого POI."""
        latest = get_latest_itinerary(self.trip_id)
        upsert_item_feedback(
            self.trip_id,
            int(latest["id"]),
            "route_stops",
            0,
            make_route_stop_key(CATHEDRAL_POI_ID),
            -1,
        )
        base = get_latest_itinerary(self.trip_id)["program"]

        snap = snapshot_route_feedback(base, self.trip_id, "routes")
        assert snap is not None
        self.assertIn(CATHEDRAL_POI_ID, snap["banned_poi_ids"])

        routes1, _ = resolve_routes_program(
            self.messages,
            base.get("routes"),
            base_program=base,
            trip_id=self.trip_id,
            expected_city="Саранск",
            rebuild_scope="routes",
            route_feedback_snapshot=snap,
        )
        prog1 = {**base, "routes": routes1.model_dump()}
        save_itinerary_version(self.trip_id, prog1, scope="routes")

        self.assertNotIn(CATHEDRAL_POI_ID, self._all_route_poi_ids(prog1))
        self.assertEqual(
            list_item_feedback_by_section(self.trip_id, "route_stops"),
            {make_route_stop_key(CATHEDRAL_POI_ID): -1},
        )

        base2 = get_latest_itinerary(self.trip_id)["program"]
        state = self.service.prepare_continue_trip(self.trip_id, "routes")
        snap2 = state["route_feedback_snapshot"]
        assert snap2 is not None
        self.assertIn(CATHEDRAL_POI_ID, snap2["banned_poi_ids"])

        routes2, _ = resolve_routes_program(
            self.messages,
            base2.get("routes"),
            base_program=base2,
            trip_id=self.trip_id,
            expected_city="Саранск",
            rebuild_scope="routes",
            route_feedback_snapshot=snap2,
        )
        prog2 = {**base2, "routes": routes2.model_dump()}
        all_poi = self._all_route_poi_ids(prog2)
        self.assertNotIn(CATHEDRAL_POI_ID, all_poi)
        self.assertNotIn(MONUMENT_POI_ID, all_poi)

    def test_disliked_route_bans_its_stops(self) -> None:
        """👎 на вариант маршрута тоже исключает его остановки."""
        from models.routes import RouteProgram
        from program.parse_items import parse_program_sections
        from program.route_feedback import collect_leisure_poi_ids

        base = get_latest_itinerary(self.trip_id)["program"]
        parsed = parse_program_sections(base)
        route_text = parsed.routes.items[0]
        self.service.set_item_feedback(
            self.trip_id,
            section="routes",
            item_key=make_item_key("routes", route_text),
            vote=-1,
        )
        cases = RouteProgram.model_validate(base["routes"]).cases
        _, banned_with_route, _ = rebuild_poi_preferences(
            self.trip_id,
            self.materials,
            [],
            disliked_routes=[cases[0]],
        )
        self.assertTrue(collect_leisure_poi_ids([cases[0]]) <= banned_with_route)


if __name__ == "__main__":
    unittest.main()
