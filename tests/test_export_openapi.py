"""Тест экспорта OpenAPI-схемы."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.export_openapi import export_openapi


class TestExportOpenapi(unittest.TestCase):
    def test_export_contains_trips_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "openapi.json"
            export_openapi(output=out)
            schema = json.loads(out.read_text(encoding="utf-8"))
        paths = schema.get("paths", {})
        self.assertIn("/api/trips", paths)
        self.assertIn("delete", paths["/api/trips/{trip_id}"])
        self.assertIn("/api/runs/{run_id}", paths)
        self.assertEqual(schema["info"]["title"], "Туристический ассистент API")


if __name__ == "__main__":
    unittest.main()
