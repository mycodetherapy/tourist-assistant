"""Тесты правил жд/автобус по расстоянию."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from search.transport_codes import (
    BUS_MAX_ROUTE_KM,
    bus_ticket_required,
    city_pair_distance_km,
    required_ticket_markers,
)


class TestTransportCodesDistance(unittest.TestCase):
    def test_bus_not_required_over_650_km(self) -> None:
        with patch(
            "search.transport_codes.city_pair_distance_km", return_value=800.0
        ):
            self.assertFalse(bus_ticket_required("Москва", "Казань"))
            self.assertEqual(
                required_ticket_markers("Москва", "Казань"),
                ("самол", "поезд"),
            )

    def test_bus_required_at_650_km_boundary(self) -> None:
        with patch("search.transport_codes.city_pair_distance_km", return_value=642.0):
            self.assertTrue(bus_ticket_required("Москва", "Йошкар-Ола"))

    def test_bus_required_under_650_km(self) -> None:
        with (
            patch("search.transport_codes.city_pair_distance_km", return_value=400.0),
            patch("search.airport_routing.city_pair_distance_km", return_value=400.0),
        ):
            self.assertTrue(bus_ticket_required("Москва", "Тверь"))
            self.assertEqual(
                required_ticket_markers("Москва", "Тверь"),
                ("поезд", "автобус"),
            )

    def test_international_only_plane(self) -> None:
        self.assertEqual(
            required_ticket_markers("Москва", "Стамбул"),
            ("самол",),
        )

    def test_bus_max_constant(self) -> None:
        self.assertEqual(BUS_MAX_ROUTE_KM, 650)

    def test_city_pair_distance_cached(self) -> None:
        city_pair_distance_km.cache_clear()
        with patch("search.osm.nominatim.resolve_city_center") as mock_center:
            mock_center.side_effect = [
                type("C", (), {"lat": 55.75, "lon": 37.62})(),
                type("C", (), {"lat": 55.79, "lon": 49.12})(),
            ]
            d1 = city_pair_distance_km("Москва", "Казань")
            d2 = city_pair_distance_km("Москва", "Казань")
        self.assertIsNotNone(d1)
        assert d1 is not None
        self.assertGreater(d1, 700)
        self.assertEqual(d1, d2)
        self.assertEqual(mock_center.call_count, 2)


if __name__ == "__main__":
    unittest.main()
