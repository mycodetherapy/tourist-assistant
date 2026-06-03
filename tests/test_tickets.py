"""Тесты билетов: парсинг дат, deep links, контракт tool."""

from __future__ import annotations

import json
import unittest
from datetime import date
from unittest.mock import patch

from models.tickets import OfferSource, TicketOffer, TicketsSearchOutput, TransportMode
from planning.dates import parse_trip_dates
from search.city_codes import city_to_iata
from search.ticket_links import build_ticket_offers, format_offers_summary
from search.providers.avia import fetch_avia_offers
from search.tickets_search import run_tickets_search
from search.tool_logging import parse_tool_result


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

    def test_build_offers_saratov_moscow(self) -> None:
        parsed = parse_trip_dates("18-21 июня 2026")
        offers = build_ticket_offers("Саратов", "Москва", parsed)
        modes = {o.mode for o in offers}
        self.assertIn(TransportMode.plane, modes)
        self.assertIn(TransportMode.train, modes)
        self.assertIn(TransportMode.bus, modes)
        providers = {o.provider for o in offers}
        self.assertEqual(
            {p for o in offers if o.mode == TransportMode.plane for p in [o.provider]},
            {"Aviasales"},
        )
        self.assertNotIn("Яндекс", " ".join(providers))
        self.assertNotIn("Google", " ".join(providers))
        self.assertNotIn("Skyscanner", " ".join(providers))
        self.assertNotIn("E-traffic", " ".join(providers))

    def test_tutu_train_url_format(self) -> None:
        parsed = parse_trip_dates("18 июня 2026")
        offers = build_ticket_offers("Саратов", "Москва", parsed)
        tutu = next(o for o in offers if o.provider == "Tutu.ru")
        self.assertEqual(
            tutu.booking_url,
            "https://www.tutu.ru/poezda/Saratov/Moskva/?date=18.06.2026&travelers=1",
        )

    def test_rzd_url_format(self) -> None:
        parsed = parse_trip_dates("18 июня 2026")
        offers = build_ticket_offers("Саратов", "Москва", parsed)
        rzd = next(o for o in offers if o.provider == "РЖД")
        self.assertEqual(
            rzd.booking_url,
            "https://ticket.rzd.ru/searchresults/v/1/"
            "5a13ba86340c745ca1e7eb03/5a323c29340c7441a0a556bb/"
            "2026-6-18?adult=1",
        )

    def test_bus_tutu_one_way_url(self) -> None:
        parsed = parse_trip_dates("15 июня 2026")
        offers = build_ticket_offers("Саратов", "Москва", parsed)
        bus = next(o for o in offers if o.provider == "Bus.tutu.ru")
        self.assertTrue(bus.booking_url.startswith("https://bus.tutu.ru/raspisanie/gorod_Saratov/gorod_Moskva/"))
        self.assertIn("date=15.06.2026", bus.booking_url)
        self.assertIn("from=1433947", bus.booking_url)
        self.assertIn("to=1447874", bus.booking_url)
        self.assertIn("travelers=1", bus.booking_url)
        self.assertIn("amount=1", bus.booking_url)

    def test_summary_no_duplicate_price(self) -> None:
        parsed = parse_trip_dates("1-4 августа 2026")
        api_offer = TicketOffer(
            mode=TransportMode.plane,
            source=OfferSource.api,
            is_direct=True,
            transfers=0,
            price_from=8469,
            booking_url="https://www.aviasales.ru/search/test",
            label="DP 6825, прямой, от 8469 ₽",
            provider="Aviasales API",
        )
        summary = format_offers_summary("Москва", "Санкт-Петербург", parsed, [api_offer])
        self.assertEqual(summary.count("от 8469 ₽"), 1)

    def test_aviasales_url_contains_dates(self) -> None:
        parsed = parse_trip_dates("15-18 июля 2026")
        offers = build_ticket_offers("Саратов", "Сыктывкар", parsed)
        avia = next(o for o in offers if o.provider == "Aviasales")
        self.assertIn("aviasales.ru/search/", avia.booking_url)
        self.assertIn("GSV1507", avia.booking_url.upper())
        self.assertIn("SCW1807", avia.booking_url.upper())
        self.assertNotIn("?t=", avia.booking_url)


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
        self.assertIn("/search/", offers[0].booking_url)
        self.assertNotIn("?t=", offers[0].booking_url)

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
