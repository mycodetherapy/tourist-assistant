"""Тест OpenAPI-схемы (статический docs/openapi.json)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPENAPI = ROOT / "docs" / "openapi.json"


class TestOpenapiSchema(unittest.TestCase):
    def test_schema_contains_trips_paths(self) -> None:
        self.assertTrue(OPENAPI.is_file(), "docs/openapi.json missing")
        schema = json.loads(OPENAPI.read_text(encoding="utf-8"))
        paths = schema.get("paths", {})
        self.assertIn("/api/trips", paths)
        self.assertIn("delete", paths["/api/trips/{trip_id}"])
        self.assertIn("/api/runs/{run_id}", paths)


if __name__ == "__main__":
    unittest.main()
