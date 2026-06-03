"""URL поиска Aviasales: общая выдача по маршруту и датам."""

from __future__ import annotations

from datetime import date
from urllib.parse import urlencode

AVIASALES_SITE = "https://www.aviasales.ru"


def build_aviasales_search_url(
    origin_iata: str,
    destination_iata: str,
    departure: date,
    return_date: date | None = None,
) -> str:
    """
    Страница со всеми рейсами, например:
    /search/GSV1507MOW18071?origin_airports=0&destination_airports=1
    """
    o = origin_iata.strip().upper()
    d = destination_iata.strip().upper()
    dep_part = departure.strftime("%d%m")
    if return_date:
        path = f"{o}{dep_part}{d}{return_date.strftime('%d%m')}"
    else:
        path = f"{o}{dep_part}{d}"
    query = urlencode({"origin_airports": "0", "destination_airports": "1"})
    return f"{AVIASALES_SITE}/search/{path}?{query}"
