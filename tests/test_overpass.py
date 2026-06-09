"""Тесты Overpass QL и зеркал."""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

from search.osm.overpass import (
    _DEFAULT_OVERPASS_ENDPOINTS,
    _batched_bbox_queries,
    _bbox_clause,
    _overpass_endpoints,
    _run_overpass,
    fetch_overpass_leisure,
)


class OverpassQueryTests(unittest.TestCase):
    def test_bbox_clause_order_is_south_west_north_east(self) -> None:
        self.assertEqual(_bbox_clause((39.8, 57.5, 40.0, 57.7)), "57.5,39.8,57.7,40.0")

    def test_batched_queries_use_native_bbox_not_turbo_geocode(self) -> None:
        bbox = (39.817, 57.585, 39.969, 57.666)
        queries = _batched_bbox_queries(bbox)
        joined = "\n".join(queries)
        self.assertGreaterEqual(len(queries), 3)
        self.assertNotIn("geocodeArea", joined)
        self.assertNotIn("{{", joined)
        self.assertIn("57.585,39.817", queries[0])
        self.assertIn('node["tourism"="museum"]', queries[0])
        self.assertIn("out center tags", queries[0])

    def test_default_endpoints_prefer_kumi_mirror(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OVERPASS_URL", None)
            os.environ.pop("OVERPASS_URLS", None)
            endpoints = _overpass_endpoints()
        self.assertEqual(endpoints[0], _DEFAULT_OVERPASS_ENDPOINTS[0])
        self.assertIn("kumi.systems", endpoints[0])

    def test_overpass_url_overrides_defaults(self) -> None:
        with patch.dict(
            os.environ,
            {"OVERPASS_URL": "https://example.test/api/interpreter"},
            clear=False,
        ):
            self.assertEqual(
                _overpass_endpoints(),
                ["https://example.test/api/interpreter"],
            )

    @patch("search.osm.overpass.requests.post")
    def test_run_overpass_tries_next_mirror_on_504(self, post: MagicMock) -> None:
        fail = MagicMock(status_code=504, raise_for_status=MagicMock())
        ok = MagicMock(status_code=200, raise_for_status=MagicMock())
        ok.json.return_value = {"elements": [{"type": "node", "id": 1, "lat": 1, "lon": 2, "tags": {"name": "X"}}]}
        post.side_effect = [
            fail,
            fail,
            ok,
        ]
        with patch.dict(
            os.environ,
            {
                "OVERPASS_URLS": "https://bad.test/api/interpreter,https://good.test/api/interpreter"
            },
            clear=False,
        ):
            elements = _run_overpass('[out:json];node(1,2,3,4);out;')
        self.assertEqual(len(elements), 1)
        self.assertGreaterEqual(post.call_count, 3)


class FetchOverpassLeisureTests(unittest.TestCase):
    @patch("search.osm.overpass._fetch_bbox_elements")
    def test_city_bbox_fallback_when_walk_bbox_sparse(
        self,
        fetch_bbox: MagicMock,
    ) -> None:
        from search.osm.nominatim import CityCenter

        center = CityCenter(
            city="Ярославль",
            lon=39.89,
            lat=57.62,
            bbox=(39.72, 57.52, 40.0, 57.78),
        )
        sparse = [{"type": "node", "id": 1, "lat": 57.62, "lon": 39.89, "tags": {"tourism": "museum", "name": "Музей тест"}}]
        rich = sparse + [
            {
                "type": "node",
                "id": index,
                "lat": 57.63,
                "lon": 39.90 + index * 0.001,
                "tags": {"tourism": "attraction", "name": f"Церковь тест {index}"},
            }
            for index in range(2, 12)
        ]

        def side_effect(bbox: tuple[float, float, float, float], *, max_raw: int) -> list:
            _west, _south, east, _north = bbox
            if east < 39.99:
                return sparse
            return rich

        fetch_bbox.side_effect = side_effect
        points = fetch_overpass_leisure("Ярославль", center, max_elements=20)
        self.assertGreater(len(points), len(sparse))
        self.assertEqual(fetch_bbox.call_count, 2)


if __name__ == "__main__":
    unittest.main()
