"""URL поиска Aviasales: общая выдача по маршруту и датам."""

from __future__ import annotations

from datetime import date
from urllib.parse import urlencode

from search.ticket_passengers import TicketPassengers

AVIASALES_SITE = "https://www.aviasales.ru"


def build_aviasales_search_url(
    origin_iata: str,
    destination_iata: str,
    departure: date,
    return_date: date | None = None,
    *,
    passengers: TicketPassengers | None = None,
    affiliate_marker: str | None = None,
) -> str:
    """
    Страница со всеми рейсами, например:
    /search/GSV1507MOW18071?origin_airports=0&destination_airports=1&adults=2
    """
    o = origin_iata.strip().upper()
    d = destination_iata.strip().upper()
    dep_part = departure.strftime("%d%m")
    if return_date:
        path = f"{o}{dep_part}{d}{return_date.strftime('%d%m')}"
    else:
        path = f"{o}{dep_part}{d}"
    params: dict[str, str] = {
        "origin_airports": "0",
        "destination_airports": "1",
    }
    pax = passengers or TicketPassengers(adults=1)
    params["adults"] = str(pax.adults)
    if pax.children:
        params["children"] = str(pax.children)
    if pax.infants:
        params["infants"] = str(pax.infants)
    marker = (affiliate_marker or "").strip()
    if marker:
        params["marker"] = marker
    query = urlencode(params)
    return f"{AVIASALES_SITE}/search/{path}?{query}"
