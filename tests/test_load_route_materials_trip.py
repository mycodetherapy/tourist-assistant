"""Тесты load_route_materials из кэша trip."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agents.finalize_helpers import load_route_materials
from db.repository import create_trip, save_section_artifact
from models.routes import GeoPoint, PoiPoint, RouteMaterials
from search.route_materials_store import ROUTE_MATERIALS_SECTION
from tests.db_test_helpers import skip_unless_pg, truncate_pg_tables


@skip_unless_pg
class TestLoadRouteMaterialsFromTrip(unittest.TestCase):
    def setUp(self) -> None:
        truncate_pg_tables()

    def test_load_from_db_without_tool_message(self) -> None:
        trip_id = create_trip("Самара", "июнь", "Москва", "тест")
        materials = RouteMaterials(
            city="Самара",
            dates="июнь",
            leisure_points=[
                PoiPoint(
                    poi_id="x",
                    tag="landmarks",
                    name="Площадь",
                    coordinates=GeoPoint(lon=50.1, lat=53.2),
                    maps_url="https://example.com",
                )
            ],
        )
        save_section_artifact(
            trip_id,
            ROUTE_MATERIALS_SECTION,
            {"schema_version": 1, "materials": materials.model_dump()},
            digest="digest",
        )
        loaded = load_route_materials([], expected_city="Самара", trip_id=trip_id)
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded.city, "Самара")


if __name__ == "__main__":
    unittest.main()
