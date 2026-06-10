"""Тесты ближайшего аэропорта и порога дистанции для авиа."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from search.airport_routing import (
    PLANE_MIN_ROUTE_KM,
    avia_route_endpoints,
    avia_ticket_offered,
    nearest_domestic_iata_hub,
    resolve_avia_endpoint,
)
from search.city_codes import domestic_iata_hubs


class TestAirportRouting(unittest.TestCase):
    def test_domestic_hubs_unique_iata(self) -> None:
        hubs = domestic_iata_hubs()
        iatas = [row[1] for row in hubs]
        self.assertEqual(len(iatas), len(set(iatas)))
        self.assertIn(("казань", "KZN", "Казань"), hubs)

    def test_yoshkar_ola_redirects_to_nearest_hub(self) -> None:
        with patch(
            "search.airport_routing.nearest_domestic_iata_hub",
            return_value=("KZN", "Казань"),
        ):
            ep = resolve_avia_endpoint("Йошкар-Ола")
        self.assertIsNotNone(ep)
        assert ep is not None
        self.assertEqual(ep.iata, "KZN")
        self.assertTrue(ep.redirected)
        self.assertIn("Казань", ep.hub_label)

    def test_moscow_stays_mow(self) -> None:
        ep = resolve_avia_endpoint("Москва")
        self.assertIsNotNone(ep)
        assert ep is not None
        self.assertEqual(ep.iata, "MOW")
        self.assertFalse(ep.redirected)

    def test_nearest_hub_picks_closest_coords(self) -> None:
        hubs = (
            ("KZN", "Казань", 55.79, 49.12),
            ("GOJ", "Нижний Новгород", 56.33, 44.00),
        )
        center = type("C", (), {"lat": 56.63, "lon": 47.89})()
        with (
            patch("search.hub_coords.domestic_hub_positions", return_value=hubs),
            patch("search.osm.nominatim.resolve_city_center", return_value=center),
        ):
            hub = nearest_domestic_iata_hub("Йошкар-Ола")
        self.assertEqual(hub, ("KZN", "Казань"))

    def test_short_domestic_route_no_avia(self) -> None:
        with patch(
            "search.airport_routing.city_pair_distance_km", return_value=180.0
        ):
            self.assertFalse(avia_ticket_offered("Москва", "Тверь"))
            origin, dest = avia_route_endpoints("Москва", "Тверь")
            self.assertIsNone(origin)
            self.assertIsNone(dest)

    def test_long_domestic_route_has_avia(self) -> None:
        with patch(
            "search.airport_routing.city_pair_distance_km", return_value=820.0
        ):
            self.assertTrue(avia_ticket_offered("Москва", "Казань"))
            origin, dest = avia_route_endpoints("Москва", "Казань")
            self.assertIsNotNone(origin)
            self.assertIsNotNone(dest)
            assert origin is not None and dest is not None
            self.assertEqual(origin.iata, "MOW")
            self.assertEqual(dest.iata, "KZN")

    def test_yoshkar_ola_long_route_uses_nearest_hub(self) -> None:
        with (
            patch(
                "search.airport_routing.city_pair_distance_km", return_value=650.0
            ),
            patch(
                "search.airport_routing.nearest_domestic_iata_hub",
                return_value=("KZN", "Казань"),
            ),
        ):
            origin, dest = avia_route_endpoints("Москва", "Йошкар-Ола")
        self.assertIsNotNone(origin)
        self.assertIsNotNone(dest)
        assert dest is not None
        self.assertEqual(dest.iata, "KZN")
        self.assertTrue(dest.redirected)

    def test_international_always_offers_avia(self) -> None:
        self.assertTrue(avia_ticket_offered("Москва", "Стамбул"))

    def test_plane_min_constant(self) -> None:
        self.assertEqual(PLANE_MIN_ROUTE_KM, 500)


if __name__ == "__main__":
    unittest.main()
