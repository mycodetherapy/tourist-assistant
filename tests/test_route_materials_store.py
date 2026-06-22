"""Тесты кэша route_materials в section_artifacts."""

from __future__ import annotations

import json
import unittest

from db.repository import create_trip, get_section_artifact, save_section_artifact
from models.routes import GeoPoint, PoiPoint, RouteMaterials
from search.route_materials_store import (
    ROUTE_MATERIALS_SECTION,
    cached_materials_finalize_block,
    load_route_materials_for_trip,
    persist_route_materials_from_tool,
)
from tests.db_test_helpers import skip_unless_pg, truncate_pg_tables


def _sample_materials() -> RouteMaterials:
    return RouteMaterials(
        provider="osm",
        city="Самара",
        dates="июнь",
        leisure_points=[
            PoiPoint(
                poi_id="osm_1",
                tag="museums",
                name="Музей",
                coordinates=GeoPoint(lon=50.1, lat=53.2),
                maps_url="https://example.com",
            )
        ],
    )


@skip_unless_pg
class TestRouteMaterialsStore(unittest.TestCase):
    def setUp(self) -> None:
        truncate_pg_tables()

    def test_persist_and_load(self) -> None:
        trip_id = create_trip("Самара", "июнь", "Москва", "тест")
        materials = _sample_materials()
        tool_json = json.dumps(
            {
                "materials": materials.model_dump(),
                "materials_digest": "L1. Музей",
                "leisure_count": 1,
            },
            ensure_ascii=False,
        )
        self.assertTrue(persist_route_materials_from_tool(trip_id, tool_json))
        loaded = load_route_materials_for_trip(trip_id)
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded.city, "Самара")
        self.assertEqual(len(loaded.leisure_points), 1)

    def test_cached_finalize_block(self) -> None:
        trip_id = create_trip("Самара", "июнь", "Москва", "тест")
        materials = _sample_materials()
        save_section_artifact(
            trip_id,
            ROUTE_MATERIALS_SECTION,
            {"schema_version": 1, "materials": materials.model_dump(), "leisure_count": 1},
            digest="L1. Музей (poi_id=osm_1)",
        )
        block = cached_materials_finalize_block(trip_id)
        self.assertIsNotNone(block)
        assert block is not None
        self.assertIn("search_route_materials", block)
        self.assertIn("Музей", block)
        row = get_section_artifact(trip_id, ROUTE_MATERIALS_SECTION)
        self.assertIsNotNone(row)


if __name__ == "__main__":
    unittest.main()
