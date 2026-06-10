"""Тесты Wikidata: tiered strict + soft backfill."""

from __future__ import annotations

import unittest
import unittest.mock
from unittest.mock import patch

from search.osm.nominatim import CityCenter
from search.wikidata.places import (
    _dedupe_sparql_rows,
    _run_sparql,
    _wikidata_backfill_score,
    fetch_wikidata_leisure,
)


def _yaroslavl_center() -> CityCenter:
    return CityCenter(
        city="Ярославль",
        lon=39.8933705,
        lat=57.6263877,
        bbox=(39.7291589, 57.5257151, 40.0033332, 57.7752752),
        wikidata_id="Q2423",
    )


def _row(qid: str, name: str, lon: float, lat: float, sitelinks: int = 5) -> dict:
    return {
        "item": {"value": f"http://www.wikidata.org/entity/{qid}"},
        "itemLabel": {"value": name},
        "coord": {"value": f"Point({lon} {lat})"},
        "sitelinks": {"value": str(sitelinks)},
    }


class WikidataDedupeTests(unittest.TestCase):
    def test_dedupe_sparql_rows_keeps_first_per_qid(self) -> None:
        rows = [
            _row("Q1", "Музей A", 39.0, 57.6, 10),
            _row("Q1", "Музей A дубль", 39.0, 57.6, 5),
            _row("Q2", "Собор B", 39.1, 57.6, 8),
        ]
        deduped = _dedupe_sparql_rows(rows)
        self.assertEqual(len(deduped), 2)
        self.assertEqual(deduped[0]["itemLabel"]["value"], "Музей A")


class WikidataBackfillScoreTests(unittest.TestCase):
    def test_negative_generic_house_scores_zero(self) -> None:
        self.assertEqual(_wikidata_backfill_score("Доходный дом Работнова (Ярославль)", sitelinks=10), 0.0)

    def test_positive_ensemble_scores_high(self) -> None:
        score = _wikidata_backfill_score("Ансамбль Ильинской площади (Ярославль)", sitelinks=8)
        self.assertGreaterEqual(score, 0.6)


class FetchWikidataLeisureTests(unittest.TestCase):
    @patch("search.wikidata.places._run_sparql")
    def test_strict_landmarks_first_then_soft_backfill(self, run_sparql) -> None:
        run_sparql.return_value = [
            _row("Q1", "Церковь Покрова (Ярославль)", 39.852, 57.625, 12),
            _row("Q2", "Доходный дом Работнова (Ярославль)", 39.880, 57.627, 20),
            _row("Q3", "Ансамбль женской гимназии (Ярославль)", 39.881, 57.628, 6),
            _row("Q4", "Усадьба Носковых (Ярославль)", 39.888, 57.633, 4),
        ]
        points = fetch_wikidata_leisure(
            "Ярославль",
            _yaroslavl_center(),
            wikidata_id="Q2423",
            pool_target=4,
        )
        ids = [p.poi_id for p in points]
        self.assertIn("Q1", ids)
        self.assertIn("Q4", ids)
        self.assertNotIn("Q2", ids)
        self.assertIn("Q3", ids)
        self.assertEqual(ids.index("Q1"), 0)
        self.assertEqual(ids.index("Q4"), 1)

    @patch("search.wikidata.places._run_sparql")
    def test_relaxed_pass_adds_nearby_theatres_when_under_target(self, run_sparql) -> None:
        run_sparql.return_value = [
            _row(
                "Q1",
                "Самарский академический театр драмы",
                50.151,
                53.201,
                12,
            ),
            _row(
                "Q2",
                "Самарский театр оперы и балета",
                50.1515,
                53.2015,
                10,
            ),
            _row("Q3", "Самарский областной историко-краеведческий музей", 50.152, 53.202, 9),
        ]

        center = CityCenter(
            city="Самара",
            lon=50.15,
            lat=53.20,
            bbox=(49.95, 53.05, 50.35, 53.35),
            wikidata_id="Q894",
        )
        points = fetch_wikidata_leisure(
            "Самара",
            center,
            pool_target=3,
        )
        self.assertGreaterEqual(len(points), 2)

    @patch("search.wikidata.places._run_sparql")
    def test_embankment_query_fetched_and_tagged(self, run_sparql) -> None:
        def side_effect(query: str) -> list[dict]:
            if "набереж" in query or "embankment" in query:
                return [_row("Q99", "Волжская набережная", 50.15, 53.20, 6)]
            return []

        run_sparql.side_effect = side_effect
        points = fetch_wikidata_leisure(
            "Самара",
            CityCenter(
                city="Самара",
                lon=50.15,
                lat=53.20,
                bbox=(49.95, 53.05, 50.35, 53.35),
                wikidata_id="Q894",
            ),
            pool_target=5,
        )
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0].tag, "embankments")

    @patch("search.wikidata.places.time.sleep")
    @patch("search.wikidata.places.requests.get")
    def test_sparql_retries_on_transient_failure(self, get, _sleep) -> None:
        import requests

        ok = unittest.mock.MagicMock()
        ok.status_code = 200
        ok.json.return_value = {
            "results": {"bindings": [{"item": {"value": "http://www.wikidata.org/entity/Q1"}}]}
        }
        get.side_effect = [requests.Timeout(), ok]
        rows = _run_sparql("SELECT ?item WHERE { ?item wdt:P31 wd:Q5 }")
        self.assertEqual(len(rows), 1)
        self.assertEqual(get.call_count, 2)

    @patch("search.wikidata.places._run_sparql")
    def test_all_tier0_then_tier1_up_to_pool_target(self, run_sparql) -> None:
        rows = [
            _row(f"Q{i}", f"Музей {i} (Ярославль)", 39.85 + i * 0.001, 57.625, 10 - i)
            for i in range(3)
        ]
        rows.extend(
            [
                _row("Q10", "Ансамбль площади (Ярославль)", 39.86, 57.626, 8),
                _row("Q11", "Здание думы (Ярославль)", 39.861, 57.627, 7),
                _row("Q12", "Доходный дом (Ярославль)", 39.862, 57.628, 20),
            ]
        )
        run_sparql.return_value = rows
        points = fetch_wikidata_leisure(
            "Ярославль",
            _yaroslavl_center(),
            wikidata_id="Q2423",
            pool_target=5,
        )
        ids = [p.poi_id for p in points]
        self.assertEqual(len(ids), 5)
        self.assertTrue(all(qid in ids for qid in ("Q0", "Q1", "Q2")))
        self.assertIn("Q10", ids)
        self.assertNotIn("Q12", ids)

    @patch("search.wikidata.places._run_sparql")
    def test_tier0_above_pool_target_keeps_all_tier0(self, run_sparql) -> None:
        names = [
            "Церковь Покрова (Ярославль)",
            "Благовещенский собор (Ярославль)",
            "Никольский собор (Ярославль)",
            "Музей истории (Ярославль)",
            "Театр драмы (Ярославль)",
            "Памятник Минину (Ярославль)",
            "Парк Тысячелетия (Ярославль)",
        ]
        run_sparql.return_value = [
            _row(f"Q{i}", names[i], 39.85 + i * 0.01, 57.625, 5)
            for i in range(7)
        ]
        points = fetch_wikidata_leisure(
            "Ярославль",
            _yaroslavl_center(),
            pool_target=5,
        )
        self.assertEqual(len(points), 7)
        self.assertEqual({p.poi_id for p in points}, {f"Q{i}" for i in range(7)})

    @patch("search.wikidata.places._run_sparql")
    def test_sparql_query_orders_by_sitelinks(self, run_sparql) -> None:
        run_sparql.return_value = []
        fetch_wikidata_leisure("Ярославль", _yaroslavl_center(), pool_target=5)
        main_query = run_sparql.call_args_list[0][0][0]
        self.assertIn("ORDER BY DESC(?sitelinks)", main_query)
        emb_query = run_sparql.call_args_list[1][0][0]
        self.assertIn("набереж", emb_query)


if __name__ == "__main__":
    unittest.main()
