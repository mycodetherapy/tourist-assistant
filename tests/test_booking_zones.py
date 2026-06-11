"""Тесты зон поиска отелей вдоль маршрута."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from models.routes import GeoPoint, RouteProgram, TripRouteCase
from search.booking_zones import (
    Bbox,
    build_booking_map_url,
    compute_hotel_zones,
    pick_case_id_by_vote,
    resolve_stay_dates,
)
from search.ticket_passengers import passengers_for_travel_party
from search.yandex.poi_filters import haversine_km


def _case(
    case_id: str,
    maps_url: str,
    *,
    narratives: list[str] | None = None,
) -> TripRouteCase:
    stops = []
    for i, text in enumerate(narratives or []):
        stops.append(
            {
                "order": i + 1,
                "kind": "leisure",
                "poi_id": f"poi-{i}",
                "narrative": text,
            }
        )
    from models.routes import RouteStop

    return TripRouteCase(
        case_id=case_id,
        title=f"Маршрут {case_id}",
        summary="тест",
        stops=[RouteStop.model_validate(s) for s in stops],
        maps_route_url=maps_url,
    )


class TestResolveStayDates(unittest.TestCase):
    def test_range(self) -> None:
        checkin, checkout = resolve_stay_dates("15-18 июля 2026")
        self.assertEqual(str(checkin), "2026-07-15")
        self.assertEqual(str(checkout), "2026-07-18")

    def test_single_day_plus_one(self) -> None:
        checkin, checkout = resolve_stay_dates("18 июня 2026")
        self.assertEqual(str(checkin), "2026-06-18")
        self.assertEqual(str(checkout), "2026-06-19")


class TestPickCaseByVote(unittest.TestCase):
    def _routes(self, *case_ids: str) -> RouteProgram:
        return RouteProgram(
            cases=[TripRouteCase(case_id=cid, title=cid, summary="") for cid in case_ids]
        )

    def test_best_vote(self) -> None:
        routes = self._routes("A", "B", "C")
        picked = pick_case_id_by_vote(
            routes,
            [("A", None), ("B", 1), ("C", None)],
        )
        self.assertEqual(picked, "B")

    def test_tie_prefers_a(self) -> None:
        routes = self._routes("A", "B")
        picked = pick_case_id_by_vote(
            routes,
            [("A", 1), ("B", 1)],
        )
        self.assertEqual(picked, "A")

    def test_default_a_without_votes(self) -> None:
        routes = self._routes("A", "B", "C")
        picked = pick_case_id_by_vote(routes, [("A", None), ("B", None), ("C", None)])
        self.assertEqual(picked, "A")


class TestBookingMapUrl(unittest.TestCase):
    def test_required_params(self) -> None:
        bbox = Bbox(south=55.74, north=55.76, west=49.10, east=49.14)
        url = build_booking_map_url(
            city="Казань",
            checkin=resolve_stay_dates("15-18 июля 2026")[0],
            checkout=resolve_stay_dates("15-18 июля 2026")[1],
            adults=2,
            bbox=bbox,
        )
        self.assertIn("booking.com/searchresults.html", url)
        self.assertIn("ss=%D0%9A%D0%B0%D0%B7%D0%B0%D0%BD%D1%8C", url)
        self.assertIn("map=1", url)
        self.assertIn("bounding_box_north=", url)
        self.assertIn("checkin=2026-07-15", url)
        self.assertIn("group_adults=2", url)


class TestComputeHotelZones(unittest.TestCase):
    def test_compact_route_single_zone(self) -> None:
        url = (
            "https://yandex.ru/maps/?mode=routes&rtext="
            "55.7520,49.1060~55.7540,49.1100~55.7560,49.1140&rtt=pd"
        )
        case = _case("A", url, narratives=["Кремль", "Площадь", "Набережная"])
        zones = compute_hotel_zones(
            case,
            city="Казань",
            dates_raw="15-18 июля 2026",
            passengers=passengers_for_travel_party("couple"),
            trip_id=1,
        )
        self.assertEqual(len(zones), 1)
        self.assertIn("Кремль", zones[0].label)
        self.assertTrue(zones[0].booking_url.startswith("https://www.booking.com/"))

    def test_long_route_multiple_zones(self) -> None:
        points = [
            GeoPoint(lat=55.75, lon=49.10),
            GeoPoint(lat=55.76, lon=49.12),
            GeoPoint(lat=55.78, lon=49.18),
            GeoPoint(lat=55.80, lon=49.24),
        ]
        span = max(haversine_km(points[i], points[j]) for i in range(len(points)) for j in range(i + 1, len(points)))
        self.assertGreater(span, 3.0)
        rtext = "~".join(f"{p.lat},{p.lon}" for p in points)
        url = f"https://yandex.ru/maps/?mode=routes&rtext={rtext}&rtt=pd"
        case = _case("B", url, narratives=["A", "B", "C", "D"])
        zones = compute_hotel_zones(
            case,
            city="Казань",
            dates_raw="15-18 июля 2026",
            passengers=passengers_for_travel_party("couple"),
            trip_id=2,
        )
        self.assertGreaterEqual(len(zones), 2)

    @patch("search.booking_zones.create_partner_links")
    @patch("search.booking_zones.partner_links_available", return_value=True)
    @patch("search.booking_zones.affiliate_booking_enabled", return_value=True)
    def test_affiliate_wrap(
        self,
        _aff: object,
        _links_ok: object,
        mock_links: object,
    ) -> None:
        def _wrap(pairs: list[tuple[str, str]]) -> dict[str, str]:
            return {url: f"https://tp.st/wrapped-{idx}" for idx, (url, _) in enumerate(pairs, 1)}

        mock_links.side_effect = _wrap
        url = "https://yandex.ru/maps/?rtext=55.7520,49.1060~55.7540,49.1100&rtt=pd"
        case = _case("A", url)
        zones = compute_hotel_zones(
            case,
            city="Казань",
            dates_raw="15-18 июля 2026",
            passengers=passengers_for_travel_party("solo"),
            trip_id=3,
        )
        self.assertEqual(len(zones), 1)
        self.assertTrue(zones[0].booking_url.startswith("https://tp.st/wrapped-"))
        mock_links.assert_called_once()


if __name__ == "__main__":
    unittest.main()
