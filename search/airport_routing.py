"""IATA для Aviasales: ближайший аэропорт и порог дистанции для авиа."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from search.city_codes import city_to_iata, is_foreign_destination
from search.hub_coords import domestic_hub_positions
from search.transport_codes import (
    city_pair_distance_km,
    ground_transport_available,
    haversine_km,
)

# Короткие внутренние маршруты — ж/д и автобус, без самолёта.
PLANE_MIN_ROUTE_KM = 500


@dataclass(frozen=True)
class AviaEndpoint:
    """Точка поиска авиабилетов на Aviasales."""

    iata: str
    hub_label: str
    requested_city: str
    redirected: bool


@lru_cache(maxsize=256)
def nearest_domestic_iata_hub(city: str) -> tuple[str, str] | None:
    """Ближайший аэропорт-хаб (IATA, подпись) для города без IATA в справочнике."""
    if is_foreign_destination(city):
        return None
    from search.osm.nominatim import resolve_city_center

    center = resolve_city_center(city)
    if center is None:
        return None
    hubs = domestic_hub_positions()
    if not hubs:
        return None
    best_iata = ""
    best_label = ""
    best_dist = float("inf")
    for iata, label, lat, lon in hubs:
        dist = haversine_km(center.lat, center.lon, lat, lon)
        if dist < best_dist:
            best_dist = dist
            best_iata = iata
            best_label = label
    if not best_iata:
        return None
    return best_iata, best_label


def resolve_avia_endpoint(city: str) -> AviaEndpoint | None:
    """IATA для Aviasales; для городов без IATA — ближайший хаб из справочника."""
    cleaned = city.strip()
    if not cleaned:
        return None
    iata = city_to_iata(cleaned)
    if iata:
        return AviaEndpoint(
            iata=iata,
            hub_label=cleaned,
            requested_city=cleaned,
            redirected=False,
        )
    hub = nearest_domestic_iata_hub(cleaned)
    if not hub:
        return None
    hub_iata, hub_label = hub
    return AviaEndpoint(
        iata=hub_iata,
        hub_label=hub_label,
        requested_city=cleaned,
        redirected=True,
    )


def avia_ticket_offered(origin: str, destination: str) -> bool:
    """
    Самолёт имеет смысл на длинных или зарубежных маршрутах.
    < PLANE_MIN_ROUTE_KM при доступном ж/д — только поезд/автобус.
    """
    if is_foreign_destination(origin) or is_foreign_destination(destination):
        return True
    if not ground_transport_available(origin, destination):
        return True
    distance = city_pair_distance_km(origin, destination)
    if distance is None:
        return True
    return distance >= PLANE_MIN_ROUTE_KM


def avia_route_endpoints(
    origin_city: str,
    destination_city: str,
) -> tuple[AviaEndpoint | None, AviaEndpoint | None]:
    """Пара IATA для API/deep link или (None, None) если авиа не предлагаем."""
    if not avia_ticket_offered(origin_city, destination_city):
        return None, None
    return resolve_avia_endpoint(origin_city), resolve_avia_endpoint(destination_city)
