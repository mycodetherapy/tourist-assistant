"""Тесты affiliate-обёртки и метрик."""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from db import create_trip, init_db
from db.affiliate_repository import (
    get_affiliate_metrics,
    log_affiliate_click,
    log_affiliate_exposure,
)
from search.affiliate.programs import detect_provider
from search.affiliate.wrap import wrap_aviasales_with_marker, wrap_tickets_markdown


class TestAffiliatePrograms(unittest.TestCase):
    def test_detect_aviasales(self) -> None:
        provider = detect_provider(
            "https://www.aviasales.ru/search/GSV1507MOW1807?adults=2"
        )
        self.assertIsNotNone(provider)
        assert provider is not None
        self.assertEqual(provider.key, "aviasales")

    def test_detect_tutu_bus(self) -> None:
        provider = detect_provider(
            "https://bus.tutu.ru/raspisanie/moscow/spb/?date=01.07.2026"
        )
        self.assertIsNotNone(provider)
        assert provider is not None
        self.assertEqual(provider.key, "tutu_bus")

    def test_rzd_not_detected(self) -> None:
        self.assertIsNone(
            detect_provider("https://ticket.rzd.ru/searchresults/v/1/2000000/2004000/2026-7-15")
        )


class TestAffiliateWrap(unittest.TestCase):
    def test_marker_fallback(self) -> None:
        url = "https://www.aviasales.ru/search/GSV1507MOW1807?adults=2"
        with patch.dict(
            os.environ,
            {
                "AFFILIATE_ENABLED": "true",
                "AFFILIATE_AVIASALES": "true",
                "TRAVELPAYOUTS_MARKER": "999888",
                "TRAVELPAYOUTS_TRS": "",
            },
            clear=False,
        ):
            wrapped = wrap_aviasales_with_marker(url)
        self.assertIn("marker=999888", wrapped)

    def test_wrap_markdown_without_trs(self) -> None:
        md = (
            "**Самолёт:**\n"
            "[Aviasales: Москва → Казань]"
            "(https://www.aviasales.ru/search/MOW1507KZN1807?adults=2)"
        )
        with (
            patch.dict(
                os.environ,
                {
                    "AFFILIATE_ENABLED": "true",
                    "AFFILIATE_AVIASALES": "true",
                    "AFFILIATE_TUTU_BUS": "true",
                    "TRAVELPAYOUTS_MARKER": "12345",
                    "TRAVELPAYOUTS_TRS": "",
                    "DATABASE_PATH": "",
                },
                clear=False,
            ),
            tempfile.TemporaryDirectory() as tmp,
        ):
            os.environ["DATABASE_PATH"] = f"{tmp}/test.db"
            init_db()
            trip_id = create_trip("Казань", "июль 2026", "Москва", "test")
            result = wrap_tickets_markdown(md, trip_id=trip_id)
        self.assertIn("marker=12345", result)
        self.assertNotIn(
            "(https://www.aviasales.ru/search/MOW1507KZN1807?adults=2)", result
        )

    def test_partner_links_api_used_when_trs_set(self) -> None:
        md = (
            "[Tutu bus](https://bus.tutu.ru/raspisanie/a/b/?date=01.07.2026)"
        )
        with (
            patch.dict(
                os.environ,
                {
                    "AFFILIATE_ENABLED": "true",
                    "AFFILIATE_TUTU_BUS": "true",
                    "TRAVELPAYOUTS_MARKER": "12345",
                    "TRAVELPAYOUTS_TRS": "999",
                    "TRAVELPAYOUTS_API_KEY": "token",
                    "DATABASE_PATH": "",
                },
                clear=False,
            ),
            patch(
                "search.affiliate.wrap.create_partner_links",
                return_value={
                    "https://bus.tutu.ru/raspisanie/a/b/?date=01.07.2026": "https://tp.st/abc"
                },
            ) as mock_create,
            tempfile.TemporaryDirectory() as tmp,
        ):
            os.environ["DATABASE_PATH"] = f"{tmp}/test.db"
            init_db()
            trip_id = create_trip("СПб", "август 2026", "Москва", "test")
            result = wrap_tickets_markdown(md, trip_id=trip_id)
        mock_create.assert_called_once()
        self.assertIn("https://tp.st/abc", result)


class TestAffiliateMetrics(unittest.TestCase):
    def test_exposure_and_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["DATABASE_PATH"] = f"{tmp}/test.db"
            init_db()
            trip_id = create_trip("Казань", "июль 2026", "Москва", "test")
            log_affiliate_exposure(
                trip_id,
                channel="tickets",
                provider="aviasales",
                provider_label="Aviasales",
                sub_id="trip_1_tickets_aviasales",
            )
            metrics = get_affiliate_metrics()
            self.assertEqual(metrics["summary"]["trips_with_affiliate_links"], 1)
            self.assertEqual(metrics["summary"]["local_clicks"], 0)

    def test_local_click_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["DATABASE_PATH"] = f"{tmp}/test.db"
            init_db()
            trip_id = create_trip("Казань", "июль 2026", "Москва", "test")
            log_affiliate_click(
                trip_id,
                target_url="https://www.aviasales.ru/search/MOW0707KZN?marker=1",
                provider="aviasales",
                sub_id="trip_1_tickets_aviasales",
            )
            metrics = get_affiliate_metrics()
            self.assertEqual(metrics["summary"]["local_clicks"], 1)


class TestAffiliateSync(unittest.TestCase):
    def test_aggregate_statistics_rows(self) -> None:
        from services.affiliate_sync import _aggregate_statistics_rows

        clicks = [
            {"date": "2026-06-01", "campaign_id": 100, "sub_id": "trip_1_tickets_aviasales"},
            {"date": "2026-06-01", "campaign_id": 100, "sub_id": "trip_1_tickets_aviasales"},
        ]
        actions = [
            {
                "date": "2026-06-01",
                "campaign_id": 100,
                "sub_id": "trip_1_tickets_aviasales",
                "paid_profit_rub": 120.5,
                "state": "paid",
            }
        ]
        rows = _aggregate_statistics_rows(clicks, actions)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["clicks"], 2)
        self.assertEqual(row["bookings"], 1)
        self.assertAlmostEqual(row["revenue_rub"], 120.5)


if __name__ == "__main__":
    unittest.main()
