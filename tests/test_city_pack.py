"""Тесты city pack catalog и готовности."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config.city_catalog import is_catalog_city, resolve_city_slug
from search.osm.city_pack import is_pack_ready


class CityCatalogTests(unittest.TestCase):
    def test_resolve_kazan(self) -> None:
        self.assertEqual(resolve_city_slug("Казань"), "kazan")
        self.assertEqual(resolve_city_slug("kazan"), "kazan")

    def test_resolve_yoshkar_ola(self) -> None:
        self.assertEqual(resolve_city_slug("Йошкар-Ола"), "yoshkar-ola")

    def test_resolve_samara(self) -> None:
        self.assertEqual(resolve_city_slug("Самара"), "samara")

    def test_catalog_city(self) -> None:
        self.assertTrue(is_catalog_city("Казань"))
        self.assertFalse(is_catalog_city("Несуществующий"))


class PackReadyTests(unittest.TestCase):
    def test_pack_ready_with_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slug = "test-city"
            pack = root / "cities" / slug
            pack.mkdir(parents=True)
            (pack / "meta.json").write_text("{}", encoding="utf-8")
            db = pack / "poi.sqlite"
            conn = sqlite3.connect(db)
            conn.execute(
                "CREATE TABLE poi (poi_id TEXT PRIMARY KEY, name TEXT, lon REAL, lat REAL, "
                "leisure_tag TEXT, maps_url TEXT, address TEXT, osm_tags_json TEXT)"
            )
            conn.commit()
            conn.close()

            with patch("search.osm.city_pack.city_pack_dir", return_value=pack):
                with patch("config.city_catalog.get_city_pack_spec", return_value=None):
                    self.assertTrue(is_pack_ready(slug))


if __name__ == "__main__":
    unittest.main()
