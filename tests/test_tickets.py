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


def _expected_tickets_provider(avia_api_status: str) -> str:
    """Тот же контракт, что в search/tool_logging.py для category=tickets."""
    return "travelpayouts" if avia_api_status == "ok" else "deep_links"


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

    def test_moscow_istanbul_iata(self) -> None:
        self.assertEqual(city_to_iata("Москва"), "MOW")
        self.assertEqual(city_to_iata("Стамбул"), "IST")
        self.assertEqual(city_to_iata("Istanbul"), "IST")

    def test_build_offers_moscow_tver_no_plane(self) -> None:
        parsed = parse_trip_dates("10-12 августа 2026")
        with patch(
            "search.airport_routing.city_pair_distance_km", return_value=180.0
        ):
            offers = build_ticket_offers("Москва", "Тверь", parsed)
        modes = {o.mode for o in offers}
        self.assertNotIn(TransportMode.plane, modes)
        self.assertIn(TransportMode.train, modes)

    def test_build_offers_moscow_yoshkar_ola_kazan_iata(self) -> None:
        parsed = parse_trip_dates("10-12 августа 2026")
        with (
            patch(
                "search.airport_routing.city_pair_distance_km", return_value=650.0
            ),
            patch(
                "search.airport_routing.nearest_domestic_iata_hub",
                return_value=("KZN", "Казань"),
            ),
        ):
            offers = build_ticket_offers("Москва", "Йошкар-Ола", parsed)
        avia = next(o for o in offers if o.mode == TransportMode.plane)
        self.assertIn("KZN1208", avia.booking_url.upper())
        self.assertIn("аэропорт Казань", avia.label)

    def test_run_short_route_skips_plane(self) -> None:
        with patch(
            "search.airport_routing.city_pair_distance_km", return_value=180.0
        ):
            raw = run_tickets_search("Москва", "Тверь", "10-12 августа 2026")
        modes = {o.mode for o in raw.offers}
        self.assertNotIn(TransportMode.plane, modes)
        self.assertIn("короче 500", (raw.instruction or "").lower())
        self.assertIn("самолёт не предлагаем", (raw.warning or "").lower())

    def test_build_offers_moscow_novosibirsk_no_bus(self) -> None:
        parsed = parse_trip_dates("7-8 июля 2026")
        with patch(
            "search.transport_codes.city_pair_distance_km", return_value=2800.0
        ):
            offers = build_ticket_offers("Москва", "Новосибирск", parsed)
        modes = {o.mode for o in offers}
        self.assertIn(TransportMode.plane, modes)
        self.assertIn(TransportMode.train, modes)
        self.assertNotIn(TransportMode.bus, modes)

    def test_build_offers_moscow_istanbul(self) -> None:
        parsed = parse_trip_dates("1-4 июля 2026")
        offers = build_ticket_offers("Москва", "Стамбул", parsed)
        self.assertEqual(len(offers), 1)
        avia = offers[0]
        self.assertEqual(avia.provider, "Aviasales")
        self.assertIn("aviasales.ru/search/", avia.booking_url)
        self.assertIn("MOW0107", avia.booking_url.upper())
        self.assertIn("IST0407", avia.booking_url.upper())

    def test_build_offers_saratov_moscow(self) -> None:
        parsed = parse_trip_dates("18-21 июня 2026")
        with patch(
            "search.providers.tutu_bus.resolve_tutu_bus_city",
            side_effect=lambda c: {
                "Саратов": ("gorod_Saratov", "1433947"),
                "Москва": ("gorod_Moskva", "1447874"),
            }.get(c),
        ):
            offers = build_ticket_offers("Саратов", "Москва", parsed)
        modes = {o.mode for o in offers}
        self.assertIn(TransportMode.plane, modes)
        self.assertIn(TransportMode.train, modes)
        self.assertNotIn(TransportMode.bus, modes)
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
        offers = build_ticket_offers("Саратов", "Москва", parsed, travel_party="solo")
        tutu = next(o for o in offers if o.provider == "Tutu.ru")
        self.assertIn("date=18.06.2026", tutu.booking_url)
        self.assertIn("travelers=1", tutu.booking_url)

    def test_rzd_url_format(self) -> None:
        parsed = parse_trip_dates("18 июня 2026")
        offers = build_ticket_offers("Саратов", "Москва", parsed, travel_party="solo")
        rzd = next(o for o in offers if o.provider == "РЖД")
        self.assertEqual(
            rzd.booking_url,
            "https://ticket.rzd.ru/searchresults/v/1/"
            "5a13ba86340c745ca1e7eb03/5a323c29340c7441a0a556bb/"
            "2026-6-18?adult=1",
        )

    def test_bus_tutu_one_way_url(self) -> None:
        parsed = parse_trip_dates("15 июня 2026")
        with (
            patch(
                "search.providers.tutu_bus.resolve_tutu_bus_city",
                side_effect=lambda c: {
                    "Саратов": ("gorod_Saratov", "1433947"),
                    "Москва": ("gorod_Moskva", "1447874"),
                }.get(c),
            ),
            patch("search.transport_codes.city_pair_distance_km", return_value=400.0),
        ):
            offers = build_ticket_offers("Саратов", "Москва", parsed, travel_party="solo")
        bus = next(o for o in offers if o.provider == "Bus.tutu.ru")
        self.assertTrue(bus.booking_url.startswith("https://bus.tutu.ru/raspisanie/gorod_Saratov/gorod_Moskva/"))
        self.assertIn("date=15.06.2026", bus.booking_url)
        self.assertIn("from=1433947", bus.booking_url)
        self.assertIn("to=1447874", bus.booking_url)
        self.assertIn("travelers=1", bus.booking_url)
        self.assertIn("amount=1", bus.booking_url)

    def test_travel_party_couple_aviasales(self) -> None:
        parsed = parse_trip_dates("15-18 июля 2026")
        offers = build_ticket_offers("Саратов", "Сыктывкар", parsed, travel_party="couple")
        avia = next(o for o in offers if o.provider == "Aviasales")
        self.assertIn("adults=2", avia.booking_url)
        tutu = next(o for o in offers if o.provider == "Tutu.ru")
        self.assertIn("travelers=2", tutu.booking_url)

    def test_travel_party_family_passengers(self) -> None:
        parsed = parse_trip_dates("15-18 июля 2026")
        offers = build_ticket_offers("Саратов", "Москва", parsed, travel_party="family")
        avia = next(o for o in offers if o.provider == "Aviasales")
        self.assertIn("adults=2", avia.booking_url)
        self.assertIn("children=1", avia.booking_url)
        rzd = next(o for o in offers if o.provider == "РЖД")
        self.assertIn("adult=3", rzd.booking_url)

    def test_travel_party_friends_three_adults(self) -> None:
        parsed = parse_trip_dates("18 июня 2026")
        offers = build_ticket_offers("Саратов", "Москва", parsed, travel_party="friends")
        avia = next(o for o in offers if o.provider == "Aviasales")
        self.assertIn("adults=3", avia.booking_url)

    def test_travel_party_parent_child(self) -> None:
        parsed = parse_trip_dates("18 июня 2026")
        offers = build_ticket_offers("Саратов", "Москва", parsed, travel_party="parent_child")
        avia = next(o for o in offers if o.provider == "Aviasales")
        self.assertIn("adults=1", avia.booking_url)
        self.assertIn("children=1", avia.booking_url)
        rzd = next(o for o in offers if o.provider == "РЖД")
        self.assertIn("adult=2", rzd.booking_url)

    def test_travel_party_family_two(self) -> None:
        parsed = parse_trip_dates("18 июня 2026")
        with (
            patch(
                "search.providers.tutu_bus.resolve_tutu_bus_city",
                side_effect=lambda c: {
                    "Саратов": ("gorod_Saratov", "1433947"),
                    "Москва": ("gorod_Moskva", "1447874"),
                }.get(c),
            ),
            patch("search.transport_codes.city_pair_distance_km", return_value=400.0),
        ):
            offers = build_ticket_offers("Саратов", "Москва", parsed, travel_party="family_two")
        avia = next(o for o in offers if o.provider == "Aviasales")
        self.assertIn("adults=2", avia.booking_url)
        self.assertIn("children=2", avia.booking_url)
        bus = next(o for o in offers if o.provider == "Bus.tutu.ru")
        self.assertIn("travelers=4", bus.booking_url)

    def test_normalize_inline_api_flights_to_column(self) -> None:
        from search.ticket_links import normalize_tickets_markdown

        raw = (
            "**Самолёт:** [Aviasales: Москва → Пермь (2 взр., 2 реб.)](https://www.aviasales.ru/search/x) "
            "· DP 6859, прямой, от 8810 ₽ · N4 59, прямой, от 8871 ₽"
        )
        normalized = normalize_tickets_markdown(raw)
        self.assertIn("- DP 6859, прямой, от 8810 ₽", normalized)
        self.assertIn("- N4 59, прямой, от 8871 ₽", normalized)
        self.assertNotIn(" · DP", normalized)

    def test_summary_api_flights_one_per_line(self) -> None:
        parsed = parse_trip_dates("3-5 июля 2026")
        offers = [
            TicketOffer(
                mode=TransportMode.plane,
                source=OfferSource.api,
                is_direct=True,
                transfers=0,
                price_from=8810,
                booking_url="https://www.aviasales.ru/search/x",
                label="DP 6859, прямой, от 8810 ₽",
                provider="Aviasales API",
            ),
            TicketOffer(
                mode=TransportMode.plane,
                source=OfferSource.api,
                is_direct=True,
                transfers=0,
                price_from=8871,
                booking_url="https://www.aviasales.ru/search/x",
                label="N4 59, прямой, от 8871 ₽",
                provider="Aviasales API",
            ),
        ]
        summary = format_offers_summary("Казань", "Самара", parsed, offers)
        self.assertIn("**Самолёт:**", summary)
        self.assertIn("[Aviasales: Казань → Самара]", summary)
        self.assertNotIn("[Все рейсы на Aviasales]", summary)
        self.assertIn("\n- DP 6859", summary)
        self.assertIn("\n- N4 59", summary)
        self.assertNotIn(" · ", summary)

    def test_summary_api_avia_link_with_family_pax(self) -> None:
        parsed = parse_trip_dates("3-5 июля 2026")
        offers = [
            TicketOffer(
                mode=TransportMode.plane,
                source=OfferSource.api,
                is_direct=True,
                transfers=0,
                price_from=14266,
                booking_url="https://www.aviasales.ru/search/x",
                label="FV 6399, прямой, от 14266 ₽",
                provider="Aviasales API",
            ),
        ]
        from search.ticket_passengers import passengers_for_travel_party

        summary = format_offers_summary(
            "Москва",
            "Пермь",
            parsed,
            offers,
            passengers=passengers_for_travel_party("family"),
        )
        self.assertIn("[Aviasales: Москва → Пермь]", summary)

    def test_normalize_keeps_aviasales_route_link(self) -> None:
        from search.ticket_links import normalize_tickets_markdown

        raw = (
            "Маршрут: Москва → Пермь, даты: 03.07.2026 — 05.07.2026.\n"
            "**Самолёт:**\n"
            "[Aviasales: Москва → Пермь](https://www.aviasales.ru/search/x)\n"
            "- FV 6399, прямой, от 14266 ₽"
        )
        normalized = normalize_tickets_markdown(raw)
        self.assertIn(
            "[Aviasales: Москва → Пермь](https://www.aviasales.ru/search/x)",
            normalized,
        )

    def test_normalize_legacy_plain_urls(self) -> None:
        from search.ticket_links import normalize_tickets_markdown

        raw = (
            "**Поезд:**\n"
            "- Tutu (жд): Казань → Самара (2 взр.): "
            "https://www.tutu.ru/poezda/Kazan/Samara/?travelers=2&date=03.07.2026"
        )
        normalized = normalize_tickets_markdown(raw)
        self.assertIn(
            "[Tutu (жд): Казань → Самара (2 взр.)]"
            + "(https://www.tutu.ru/poezda/Kazan/Samara/?travelers=2&date=03.07.2026)",
            normalized,
        )
        self.assertNotIn(": https://www.tutu.ru", normalized)

    def test_summary_markdown_links(self) -> None:
        parsed = parse_trip_dates("3-5 июля 2026")
        with patch(
            "search.providers.tutu_bus.resolve_tutu_bus_city",
            side_effect=lambda c: {
                "Казань": ("gorod_Kazan", "1330021"),
                "Самара": ("gorod_Samara", "1321497"),
            }.get(c),
        ):
            offers = build_ticket_offers("Казань", "Самара", parsed, travel_party="couple")
            summary = format_offers_summary("Казань", "Самара", parsed, offers)
        self.assertIn("**Поезд:**\n[", summary)
        self.assertIn("](https://www.tutu.ru/poezda/", summary)
        self.assertIn("**Автобус:**\n[", summary)
        self.assertIn("](https://bus.tutu.ru/raspisanie/", summary)
        self.assertNotRegex(summary, r"\]: https://")

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
        self.assertIn("Пассажиры в ссылках:", summary)

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
    def _assert_tickets_tool_logging(
        self,
        origin: str,
        destination: str,
        dates: str,
        *,
        expected_provider: str | None = None,
    ) -> None:
        raw = run_tickets_search(origin, destination, dates)
        payload = json.loads(raw.model_dump_json())
        metrics = parse_tool_result(raw.model_dump_json())
        self.assertTrue(metrics["live_data"])
        self.assertGreater(metrics["results_count"], 0)
        provider = expected_provider or _expected_tickets_provider(
            payload["avia_api_status"]
        )
        self.assertEqual(metrics["provider"], provider)

    def test_run_includes_passenger_summary_for_family(self) -> None:
        raw = run_tickets_search(
            "Москва", "Казань", "10-12 августа 2026", travel_party="family"
        )
        self.assertIn("Пассажиры в ссылках:", raw.summary_for_llm or "")
        self.assertIn("2 взр.", raw.summary_for_llm or "")
        self.assertIn("1 реб.", raw.summary_for_llm or "")

    def test_run_returns_valid_schema(self) -> None:
        raw = run_tickets_search("Саратов", "Сыктывкар", "15-18 июля 2026")
        payload = json.loads(raw.model_dump_json())
        model = TicketsSearchOutput.model_validate(payload)
        self.assertEqual(model.schema_version, "1")
        self.assertGreater(model.offers_count, 0)
        self.assertIn(model.avia_api_status, ("disabled", "ok", "empty", "error"))

    def test_tool_logging_tickets_payload(self) -> None:
        """С ключом TRAVELPAYOUTS_API_KEY или без — provider согласован с avia_api_status."""
        self._assert_tickets_tool_logging(
            "Москва", "Казань", "10-12 августа 2026"
        )

    @patch("search.tickets_search.fetch_avia_offers", return_value=([], "disabled"))
    def test_tool_logging_provider_without_avia_api(
        self, _mock_fetch: object
    ) -> None:
        with patch.dict("os.environ", {"TRAVELPAYOUTS_API_KEY": "test-token"}):
            self._assert_tickets_tool_logging(
                "Москва",
                "Казань",
                "10-12 августа 2026",
                expected_provider="deep_links",
            )

    @patch("search.tickets_search.fetch_avia_offers")
    def test_tool_logging_provider_with_avia_api(self, mock_fetch) -> None:
        api_offer = TicketOffer(
            mode=TransportMode.plane,
            source=OfferSource.api,
            transfers=0,
            price_from=9000,
            booking_url="https://www.aviasales.ru/search/MOW1008KZN1208",
            label="SU 123, прямой, от 9000 ₽",
            provider="Aviasales API",
        )
        mock_fetch.return_value = ([api_offer], "ok")
        with patch.dict("os.environ", {"TRAVELPAYOUTS_API_KEY": "test-token"}):
            self._assert_tickets_tool_logging(
                "Москва",
                "Казань",
                "10-12 августа 2026",
                expected_provider="travelpayouts",
            )


if __name__ == "__main__":
    unittest.main()
