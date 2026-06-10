"""Тесты bus.tutu.ru: резолв городов через api-bus.tutu.ru."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from search.providers.tutu_bus import clear_tutu_bus_cache, resolve_tutu_bus_city
from search.ticket_links import build_ticket_offers
from planning.dates import parse_trip_dates
from models.tickets import TransportMode


def _geo_payload(point_id: int, translit: str) -> dict:
    return {
        "data": {
            "geopoints": [
                {
                    "id": point_id,
                    "names": [{"name": translit, "langCode": "ru@translit"}],
                }
            ]
        }
    }


class TestTutuBusGeo(unittest.TestCase):
    def setUp(self) -> None:
        clear_tutu_bus_cache()

    def tearDown(self) -> None:
        clear_tutu_bus_cache()

    @patch("search.providers.tutu_bus.requests.get")
    def test_resolve_moscow(self, mock_get) -> None:
        mock_get.return_value.json.return_value = _geo_payload(1447874, "Moskva")
        mock_get.return_value.raise_for_status = lambda: None
        self.assertEqual(resolve_tutu_bus_city("Москва"), ("gorod_Moskva", "1447874"))

    @patch("search.providers.tutu_bus.requests.get")
    def test_resolve_yoshkar_ola_slug(self, mock_get) -> None:
        mock_get.return_value.json.return_value = _geo_payload(1356140, "Joshkar-Ola")
        mock_get.return_value.raise_for_status = lambda: None
        self.assertEqual(
            resolve_tutu_bus_city("Йошкар-Ола"),
            ("gorod_Joshkar-Ola", "1356140"),
        )

    @patch("search.providers.tutu_bus.resolve_tutu_bus_city")
    @patch("search.airport_routing.nearest_domestic_iata_hub", return_value=("KZN", "Казань"))
    def test_build_offers_moscow_yoshkar_bus_url(
        self, _mock_hub: object, mock_bus_city: object
    ) -> None:
        mock_bus_city.side_effect = lambda c: {
            "Москва": ("gorod_Moskva", "1447874"),
            "Йошкар-Ола": ("gorod_Joshkar-Ola", "1356140"),
        }.get(c)
        with patch(
            "search.airport_routing.city_pair_distance_km", return_value=650.0
        ):
            offers = build_ticket_offers(
                "Москва", "Йошкар-Ола", parse_trip_dates("24-27 июля 2026")
            )
        bus = next(o for o in offers if o.mode == TransportMode.bus)
        self.assertEqual(bus.provider, "Bus.tutu.ru")
        self.assertIn("bus.tutu.ru/raspisanie/gorod_Moskva/gorod_Joshkar-Ola/", bus.booking_url)
        self.assertIn("from=1447874", bus.booking_url)
        self.assertIn("to=1356140", bus.booking_url)
        self.assertIn("date=24.07.2026", bus.booking_url)


if __name__ == "__main__":
    unittest.main()
