"""Авиа: Travelpayouts / Aviasales Data API (prices_for_dates)."""

from __future__ import annotations

import os
from typing import List, Literal, Optional, Tuple

import requests

from config import settings
from models.tickets import (
    OfferSource,
    ParsedTripDates,
    TicketOffer,
    TicketSegment,
    TransportMode,
)
from search.aviasales_urls import build_aviasales_search_url
from search.ticket_passengers import TicketPassengers

API_URL = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"

AviaApiStatus = Literal["disabled", "ok", "empty", "error"]


def _format_label(item: dict, transfers: int) -> str:
    airline = item.get("airline") or "?"
    flight = item.get("flight_number") or ""
    price = item.get("price")
    direct = "прямой" if transfers == 0 else f"{transfers} пересад."
    parts = [f"{airline} {flight}".strip(), direct]
    if price is not None:
        parts.append(f"от {int(price)} ₽")
    return ", ".join(parts)


def _map_item(
    item: dict,
    origin_iata: str,
    dest_iata: str,
    search_url: str,
) -> TicketOffer:
    transfers = int(item.get("transfers") or 0)
    origin_airport = item.get("origin_airport") or origin_iata
    dest_airport = item.get("destination_airport") or dest_iata
    return TicketOffer(
        mode=TransportMode.plane,
        source=OfferSource.api,
        is_direct=transfers == 0,
        transfers=transfers,
        segments=[
            TicketSegment(
                from_city=str(item.get("origin_name") or origin_iata),
                to_city=str(item.get("destination_name") or dest_iata),
                from_code=str(origin_airport) if origin_airport else None,
                to_code=str(dest_airport) if dest_airport else None,
                carrier=str(item.get("airline")) if item.get("airline") else None,
                number=str(item.get("flight_number")) if item.get("flight_number") else None,
            )
        ],
        price_from=int(item["price"]) if item.get("price") is not None else None,
        booking_url=search_url,
        label=_format_label(item, transfers),
        provider="Aviasales API",
        confidence="high",
    )


def fetch_avia_offers(
    origin_iata: str,
    destination_iata: str,
    parsed: ParsedTripDates,
    *,
    passengers: TicketPassengers | None = None,
    limit: Optional[int] = None,
) -> Tuple[List[TicketOffer], AviaApiStatus]:
    """
    Запрашивает билеты на конкретные даты. Без TRAVELPAYOUTS_API_KEY — disabled.
    """
    token = os.getenv("TRAVELPAYOUTS_API_KEY", "").strip()
    if not token:
        return [], "disabled"

    if not parsed.departure:
        return [], "empty"

    max_items = limit or settings.AVIA_API_LIMIT
    params: dict[str, str | int] = {
        "origin": origin_iata,
        "destination": destination_iata,
        "departure_at": parsed.departure.isoformat(),
        "currency": "rub",
        "market": "ru",
        "locale": "ru",
        "sorting": "price",
        "direct": "false",
        "limit": max_items,
        "page": 1,
        "token": token,
    }
    if parsed.return_date:
        params["return_at"] = parsed.return_date.isoformat()
        params["one_way"] = "false"
    else:
        params["one_way"] = "true"

    try:
        response = requests.get(
            API_URL,
            params=params,
            timeout=settings.AVIA_API_TIMEOUT,
        )
        response.raise_for_status()
        body = response.json()
    except (requests.RequestException, ValueError) as exc:
        print(f"  → авиа API: ошибка ({exc})")
        return [], "error"

    if not body.get("success"):
        return [], "empty"

    data = body.get("data") or []
    if not isinstance(data, list) or not data:
        return [], "empty"

    search_url = build_aviasales_search_url(
        origin_iata,
        destination_iata,
        parsed.departure,
        parsed.return_date,
        passengers=passengers,
    )
    offers = [
        _map_item(row, origin_iata, destination_iata, search_url)
        for row in data[:max_items]
    ]
    print(f"  → авиа API: {len(offers)} вариантов")
    return offers, "ok"
