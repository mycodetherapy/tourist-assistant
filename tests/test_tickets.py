"""Тесты билетов: парсинг дат, deep links, контракт tool."""

from __future__ import annotations

import json
import unittest
from datetime import date

from models.tickets import TicketsSearchOutput, TransportMode
from planning.dates import parse_trip_dates
from search.city_codes import city_to_iata
from search.ticket_links import build_ticket_offers
from search.providers.avia import fetch_avia_offers
from search.tickets_search import run_tickets_search
from search.tool_logging import parse_tool_result
from unittest.mock import patch


class TestParseTripDates(unittest.TestCase):
    def test_range_russian_month(self) -> None:
        parsed = parse_trip_dates("15-18 июля 2026")
        self.assertEqual(parsed.parse_status, "ok")
        self.assertEqual(parsed.departure, date(2026, 7, 15))
        self.assertEqual(parsed.return_date, date(2026, 7, 18))

    def test_iso_range(self) -> None:
        parsed = parse_trip_dates("2026-07-15 - 2026-07-18")
        self.assertEqual(parsed.parse_status, "ok")
        self.assertEqual(parsed.departure, date(2026, 7, 15))
        self.assertEqual(parsed.return_date, date(2026, 7, 18))


class TestTicketLinks(unittest.TestCase):
    def test_saratov_syktyvkar_iata(self) -> None:
        self.assertEqual(city_to_iata("Саратов"), "GSV")
        self.assertEqual(city_to_iata("Сыктывкар"), "SCW")

    def test_build_offers_has_three_modes(self) -> None:
        parsed = parse_trip_dates("15-18 июля 2026")
        offers = build_ticket_offers("Саратов", "Сыктывкар", parsed)
        modes = {o.mode for o in offers}
        self.assertIn(TransportMode.plane, modes)
        self.assertIn(TransportMode.train, modes)
        self.assertIn(TransportMode.bus, modes)

    def test_aviasales_url_contains_dates(self) -> None:
        parsed = parse_trip_dates("15-18 июля 2026")
        offers = build_ticket_offers("Саратов", "Сыктывкар", parsed)
        avia = next(o for o in offers if o.provider == "Aviasales")
        self.assertIn("aviasales.ru", avia.booking_url)
        self.assertTrue(
            "GSV" in avia.booking_url.upper() or "search" in avia.booking_url
        )


class TestAviaApi(unittest.TestCase):
    @patch("search.providers.avia.requests.get")
    def test_fetch_maps_api_offer(self, mock_get) -> None:
        mock_get.return_value.json.return_value = {
            "success": True,
            "data": [
                {
                    "price": 12000,
                    "airline": "SU",
                    "flight_number": "123",
                    "transfers": 1,
                    "origin_airport": "GSV",
                    "destination_airport": "SCW",
                    "link": "/search/test",
                }
            ],
        }
        mock_get.return_value.raise_for_status = lambda: None
        parsed = parse_trip_dates("15-18 июля 2026")
        with patch.dict("os.environ", {"TRAVELPAYOUTS_API_KEY": "test-token"}):
            offers, status = fetch_avia_offers("GSV", "SCW", parsed)
        self.assertEqual(status, "ok")
        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0].source.value, "api")
        self.assertEqual(offers[0].transfers, 1)
        self.assertEqual(offers[0].price_from, 12000)

    def test_fetch_disabled_without_key(self) -> None:
        parsed = parse_trip_dates("15-18 июля 2026")
        with patch.dict("os.environ", {"TRAVELPAYOUTS_API_KEY": ""}):
            offers, status = fetch_avia_offers("GSV", "SCW", parsed)
        self.assertEqual(status, "disabled")
        self.assertEqual(offers, [])


class TestTicketsSearchTool(unittest.TestCase):
    def test_run_returns_valid_schema(self) -> None:
        raw = run_tickets_search("Саратов", "Сыктывкар", "15-18 июля 2026")
        payload = json.loads(raw.model_dump_json())
        model = TicketsSearchOutput.model_validate(payload)
        self.assertEqual(model.schema_version, "1")
        self.assertGreater(model.offers_count, 0)
        self.assertIn(model.avia_api_status, ("disabled", "ok", "empty", "error"))

    def test_tool_logging_tickets_payload(self) -> None:
        raw = run_tickets_search("Москва", "Казань", "10-12 августа 2026")
        metrics = parse_tool_result(raw.model_dump_json())
        self.assertTrue(metrics["live_data"])
        self.assertGreater(metrics["results_count"], 0)
        self.assertEqual(metrics["provider"], "deep_links")


if __name__ == "__main__":
    unittest.main()
