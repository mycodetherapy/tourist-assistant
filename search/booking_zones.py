"""Зоны поиска отелей Booking.com вдоль маршрута (bbox + affiliate deep links)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable
from urllib.parse import urlencode

from models.routes import GeoPoint, RouteProgram, TripRouteCase
from planning.dates import parse_trip_dates
from search.affiliate.config import affiliate_booking_enabled, partner_links_available
from search.affiliate.links_client import create_partner_links
from search.ticket_passengers import TicketPassengers, passengers_for_travel_party
from search.yandex.poi_filters import haversine_km
from search.yandex.route_url import parse_maps_route_points

_CASE_ORDER = {"A": 0, "B": 1, "C": 2, "N-A": 10, "N-B": 11, "N-C": 12}
_COMPACT_SPAN_KM = 3.0
_LONG_SPAN_KM = 6.0
_BBOX_PADDING_KM = 0.4


@dataclass(frozen=True)
class Bbox:
    south: float
    north: float
    west: float
    east: float

    @property
    def center_lat(self) -> float:
        return (self.south + self.north) / 2

    @property
    def center_lon(self) -> float:
        return (self.west + self.east) / 2


@dataclass(frozen=True)
class HotelZone:
    zone_id: str
    label: str
    case_id: str
    center_lat: float
    center_lon: float
    booking_url: str


def _case_sort_key(case_id: str) -> int:
    return _CASE_ORDER.get(case_id, 50)


def pick_case_id_by_vote(
    routes: RouteProgram,
    route_votes: Iterable[tuple[str, int | None]],
    *,
    override: str | None = None,
) -> str:
    """Маршрут с лучшим голосом (1); при равенстве — A раньше B."""
    case_ids = [str(c.case_id) for c in routes.cases]
    if not case_ids:
        raise ValueError("Маршруты не найдены")
    if override:
        if override not in case_ids:
            raise ValueError(f"Маршрут {override} не найден")
        return override

    votes_by_id = {cid: vote for cid, vote in route_votes}
    liked = [cid for cid in case_ids if votes_by_id.get(cid) == 1]
    if liked:
        return min(liked, key=_case_sort_key)
    return min(case_ids, key=_case_sort_key)


def find_route_case(routes: RouteProgram, case_id: str) -> TripRouteCase | None:
    for case in routes.cases:
        if str(case.case_id) == case_id:
            return case
    return None


def _route_span_km(points: list[GeoPoint]) -> float:
    if len(points) < 2:
        return 0.0
    max_d = 0.0
    for i, a in enumerate(points):
        for b in points[i + 1 :]:
            max_d = max(max_d, haversine_km(a, b))
    return max_d


def _segment_count(span_km: float, point_count: int) -> int:
    if point_count < 2:
        return 1
    if span_km <= _COMPACT_SPAN_KM:
        return 1
    if span_km <= _LONG_SPAN_KM:
        return min(2, point_count)
    return min(3, point_count)


def _split_points(points: list[GeoPoint], segments: int) -> list[list[GeoPoint]]:
    if not points:
        return []
    segments = max(1, min(segments, len(points)))
    chunks: list[list[GeoPoint]] = []
    n = len(points)
    for i in range(segments):
        start = i * n // segments
        end = (i + 1) * n // segments
        chunk = points[start:end]
        if chunk:
            chunks.append(chunk)
    return chunks


def _bbox_for_points(points: list[GeoPoint], *, padding_km: float = _BBOX_PADDING_KM) -> Bbox:
    lats = [p.lat for p in points]
    lons = [p.lon for p in points]
    center_lat = sum(lats) / len(lats)
    pad_lat = padding_km / 111.0
    cos_lat = math.cos(math.radians(center_lat)) or 1e-6
    pad_lon = padding_km / (111.0 * cos_lat)
    return Bbox(
        south=min(lats) - pad_lat,
        north=max(lats) + pad_lat,
        west=min(lons) - pad_lon,
        east=max(lons) + pad_lon,
    )


def _leisure_stops(case: TripRouteCase) -> list:
    return [s for s in sorted(case.stops, key=lambda x: x.order) if s.kind == "leisure"]


def _label_for_segment(case: TripRouteCase, start_point_index: int, zone_index: int) -> str:
    leisure = _leisure_stops(case)
    if start_point_index < len(leisure):
        narrative = (leisure[start_point_index].narrative or "").strip()
        if narrative:
            return f"Рядом с {narrative}"
        poi_id = leisure[start_point_index].poi_id
        if poi_id:
            return f"Рядом с {poi_id}"
    return f"Зона {zone_index + 1}"


def build_booking_map_url(
    *,
    city: str,
    checkin: date | None,
    checkout: date | None,
    adults: int,
    bbox: Bbox,
) -> str:
    """Deep link на карту Booking.com в заданном bounding box."""
    params: dict[str, str] = {
        "ss": city.strip(),
        "group_adults": str(max(1, adults)),
        "map": "1",
        "latitude": f"{bbox.center_lat:.6f}",
        "longitude": f"{bbox.center_lon:.6f}",
        "bounding_box_north": f"{bbox.north:.6f}",
        "bounding_box_south": f"{bbox.south:.6f}",
        "bounding_box_east": f"{bbox.east:.6f}",
        "bounding_box_west": f"{bbox.west:.6f}",
    }
    if checkin:
        params["checkin"] = checkin.isoformat()
    if checkout:
        params["checkout"] = checkout.isoformat()
    return f"https://www.booking.com/searchresults.html?{urlencode(params)}"


def resolve_stay_dates(dates_raw: str) -> tuple[date | None, date | None]:
    parsed = parse_trip_dates(dates_raw)
    checkin = parsed.departure
    checkout = parsed.return_date
    if checkin and not checkout:
        checkout = checkin + timedelta(days=1)
    return checkin, checkout


def _wrap_booking_urls(
    urls: list[str],
    *,
    trip_id: int,
) -> dict[str, str]:
    if not affiliate_booking_enabled() or not partner_links_available():
        return {}
    pairs = [
        (url, f"trip_{trip_id}_hotels_booking_{idx}")
        for idx, url in enumerate(urls, start=1)
    ]
    return create_partner_links(pairs)


def compute_hotel_zones(
    case: TripRouteCase,
    *,
    city: str,
    dates_raw: str,
    passengers: TicketPassengers,
    trip_id: int,
) -> list[HotelZone]:
    """Строит 1–3 зоны поиска отелей вдоль maps_route_url маршрута."""
    points = parse_maps_route_points(case.maps_route_url)
    if not points:
        return []

    checkin, checkout = resolve_stay_dates(dates_raw)
    span = _route_span_km(points)
    n_segments = _segment_count(span, len(points))
    chunks = _split_points(points, n_segments)

    raw_urls: list[str] = []
    zone_meta: list[tuple[str, str, Bbox]] = []
    point_offset = 0
    for zone_index, chunk in enumerate(chunks):
        bbox = _bbox_for_points(chunk)
        label = _label_for_segment(case, point_offset, zone_index)
        point_offset += len(chunk)
        zone_id = f"{case.case_id}-z{zone_index + 1}"
        url = build_booking_map_url(
            city=city,
            checkin=checkin,
            checkout=checkout,
            adults=passengers.adults,
            bbox=bbox,
        )
        raw_urls.append(url)
        zone_meta.append((zone_id, label, bbox))

    wrapped = _wrap_booking_urls(raw_urls, trip_id=trip_id)
    return [
        HotelZone(
            zone_id=zone_id,
            label=label,
            case_id=str(case.case_id),
            center_lat=bbox.center_lat,
            center_lon=bbox.center_lon,
            booking_url=wrapped.get(raw_url, raw_url),
        )
        for (zone_id, label, bbox), raw_url in zip(zone_meta, raw_urls, strict=True)
    ]
