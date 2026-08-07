"""Тесты каталога городов и эфемерного OSRM (без docker)."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from models.routes import GeoPoint
from search.osrm.client import fetch_foot_route


class TestCityCatalogTiers(unittest.TestCase):
    def test_hot_and_warm_slugs(self) -> None:
        from config.city_catalog import catalog_slugs, get_city_pack_spec

        hot = catalog_slugs(tier="hot")
        warm = catalog_slugs(tier="warm")
        self.assertIn("kazan", hot)
        self.assertIn("moscow", hot)
        self.assertTrue(len(warm) > 0)
        self.assertEqual(get_city_pack_spec("kostroma").federal_district, "central")
        self.assertEqual(get_city_pack_spec("kostroma").tier, "hot")

    def test_osrm_graph_ready_false_without_files(self) -> None:
        from config.city_catalog import is_osrm_graph_ready

        with patch("config.city_catalog.city_pack_dir") as mock_dir:
            mock_dir.return_value = Path("/tmp/no-such-city-pack")
            # slug без yaml — путь через city_pack_dir
            self.assertFalse(is_osrm_graph_ready("not-a-real-slug-xyz"))


class TestEphemeralOsrmClient(unittest.TestCase):
    def test_fetch_uses_ephemeral_when_mode_set(self) -> None:
        points = [GeoPoint(lat=55.79, lon=49.12), GeoPoint(lat=55.80, lon=49.13)]
        fake = MagicMock(name="OsrmRouteResult")
        env = {
            "OSRM_MODE": "ephemeral",
            "OSRM_BASE_URL": "",
            "OSRM_URL_BY_SLUG": "",
            "OSRM_DATASET": "",
        }
        with patch.dict("os.environ", env, clear=False):
            with patch(
                "search.osrm.ephemeral.fetch_foot_route_ephemeral",
                return_value=fake,
            ) as mock_eph:
                result = fetch_foot_route(points, city="Казань")
        self.assertIs(result, fake)
        mock_eph.assert_called_once()
        self.assertEqual(mock_eph.call_args.kwargs["slug"], "kazan")

    def test_http_mode_skips_ephemeral(self) -> None:
        points = [GeoPoint(lat=55.79, lon=49.12), GeoPoint(lat=55.80, lon=49.13)]
        env = {
            "OSRM_MODE": "http",
            "OSRM_BASE_URL": "",
            "OSRM_URL_BY_SLUG": "",
            "OSRM_DATASET": "",
            "OSRM_EPHEMERAL": "",
        }
        with patch.dict("os.environ", env, clear=False):
            with patch(
                "search.osrm.ephemeral.fetch_foot_route_ephemeral"
            ) as mock_eph:
                self.assertIsNone(fetch_foot_route(points, city="Казань"))
        mock_eph.assert_not_called()


if __name__ == "__main__":
    unittest.main()
