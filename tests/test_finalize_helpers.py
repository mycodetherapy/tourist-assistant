"""Тесты подготовки finalize (маршруты из materials)."""

from __future__ import annotations

import json
import unittest

from langchain_core.messages import HumanMessage, ToolMessage

from models.routes import GeoPoint, PoiPoint, RouteMaterials
from models.schemas import ProgramDraft

from agents.finalize_helpers import (
    _coerce_program_draft,
    build_fallback_program_draft,
    prepare_finalize_messages,
    resolve_routes_program,
    slim_tool_message_for_finalize,
)


def _materials_payload() -> dict:
    materials = RouteMaterials(
        city="Казань",
        dates="июль",
        provider="fallback",
        leisure_points=[
            PoiPoint(
                poi_id="l1",
                tag="museums",
                name="Музей",
                coordinates=GeoPoint(lon=49.1, lat=55.8),
                maps_url="https://yandex.ru/maps/org/l1",
            ),
            PoiPoint(
                poi_id="l2",
                tag="landmarks",
                name="Площадь",
                coordinates=GeoPoint(lon=49.11, lat=55.81),
                maps_url="https://yandex.ru/maps/org/l2",
            ),
            PoiPoint(
                poi_id="l3",
                tag="parks",
                name="Парк",
                coordinates=GeoPoint(lon=49.12, lat=55.82),
                maps_url="https://yandex.ru/maps/org/l3",
            ),
        ],
        dining_options=[],
    )
    return {
        "materials": materials.model_dump(),
        "materials_digest": "Музей, Площадь, Парк",
        "leisure_count": 3,
        "dining_count": 0,
    }


class TestFinalizeHelpers(unittest.TestCase):
    def test_slim_route_materials_drops_heavy_fields(self) -> None:
        heavy = {
            "materials": _materials_payload()["materials"],
            "materials_digest": "Музей",
            "search": {"results": [{"url": "x", "content": "y" * 5000}] * 40},
        }
        msg = ToolMessage(
            content=json.dumps(heavy, ensure_ascii=False),
            tool_call_id="2",
            name="search_route_materials",
        )
        slim = slim_tool_message_for_finalize(msg)
        data = json.loads(str(slim.content))
        self.assertIn("materials_digest", data)

    def test_prepare_keeps_latest_route_materials_only(self) -> None:
        old = ToolMessage(
            content=json.dumps({"materials_digest": "старый"}, ensure_ascii=False),
            tool_call_id="a",
            name="search_route_materials",
        )
        new = ToolMessage(
            content=json.dumps({"materials_digest": "новый"}, ensure_ascii=False),
            tool_call_id="b",
            name="search_route_materials",
        )
        out = prepare_finalize_messages([old, new], rebuild_scope="routes")
        self.assertEqual(len(out), 1)
        self.assertIsInstance(out[0], HumanMessage)
        self.assertIn("новый", str(out[0].content))
        self.assertNotIn("старый", str(out[0].content))

    def test_prepare_routes_uses_db_cache_without_tools(self) -> None:
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        from db.connection import init_db
        from db.repository import create_trip, save_section_artifact
        from search.route_materials_store import ROUTE_MATERIALS_SECTION

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            with patch.dict("os.environ", {"DATABASE_PATH": str(db_path)}, clear=False):
                init_db()
                trip_id = create_trip("Самара", "июнь", "Москва", "тест")
                save_section_artifact(
                    trip_id,
                    ROUTE_MATERIALS_SECTION,
                    {
                        "schema_version": 1,
                        "materials": _materials_payload()["materials"],
                        "leisure_count": 2,
                    },
                    digest="L1. Музей",
                )
                out = prepare_finalize_messages([], rebuild_scope="routes", trip_id=trip_id)
        self.assertEqual(len(out), 1)
        self.assertIn("кэш", str(out[0].content).lower())
        self.assertIn("Музей", str(out[0].content))

    def test_fallback_draft_from_materials(self) -> None:
        messages = [
            ToolMessage(
                content=json.dumps(_materials_payload(), ensure_ascii=False),
                tool_call_id="m",
                name="search_route_materials",
            ),
        ]
        draft = build_fallback_program_draft(messages, city="Казань", walking_area="центр")
        self.assertEqual(len(draft.routes.cases), 3)

    def test_coerce_program_draft_from_parsed_wrapper(self) -> None:
        from unittest.mock import MagicMock

        inner = ProgramDraft(
            routes=build_fallback_program_draft([], city="Казань").routes,
            lifehacks="Совет",
        )
        wrapper = MagicMock()
        wrapper.parsed = inner
        self.assertEqual(len(_coerce_program_draft(wrapper).routes.cases), 3)
        self.assertEqual(_coerce_program_draft(inner).lifehacks, "Совет")

    def test_resolve_routes_uses_hybrid_with_draft(self) -> None:
        from agents.route_postprocess import build_fallback_route_program
        from models.routes import RouteProgram, RouteStop, TripRouteCase

        materials = RouteMaterials.model_validate(_materials_payload()["materials"])
        fallback = build_fallback_route_program(materials)
        draft = RouteProgram(
            cases=[
                TripRouteCase(
                    case_id="A",
                    title="A",
                    summary="",
                    stops=[
                        RouteStop(order=1, kind="leisure", poi_id="l2", narrative=""),
                        RouteStop(order=2, kind="leisure", poi_id="l1", narrative=""),
                        RouteStop(order=3, kind="leisure", poi_id="l3", narrative=""),
                    ],
                ),
                *fallback.cases[1:],
            ]
        )
        messages = [
            ToolMessage(
                content=json.dumps(_materials_payload(), ensure_ascii=False),
                tool_call_id="m",
                name="search_route_materials",
            ),
        ]
        program, _ = resolve_routes_program(
            messages, draft.model_dump(), base_program=None, transport="walking"
        )
        a_ids = [s.poi_id for s in program.cases[0].stops if s.kind == "leisure" and s.poi_id]
        self.assertEqual(a_ids[0], "l2")


if __name__ == "__main__":
    unittest.main()
