"""Deep links на агрегаторы билетов с датами и маршрутом."""

from __future__ import annotations

from datetime import date
from urllib.parse import quote, urlencode

from models.tickets import (
    OfferSource,
    ParsedTripDates,
    TicketOffer,
    TransportMode,
)
from search.city_codes import city_to_iata, normalize_city_name

# Транслит для slug Tutu (упрощённый).
_TRANSLIT: dict[str, str] = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "h",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "sch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}


def _slug(city: str) -> str:
    key = normalize_city_name(city)
    out: list[str] = []
    for ch in key:
        if ch.isascii() and ch.isalnum():
            out.append(ch)
        elif ch in _TRANSLIT:
            out.append(_TRANSLIT[ch])
    slug = "".join(out)
    return slug or quote(city, safe="")


def _fmt_iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


def _fmt_rzd(d: date | None) -> str | None:
    return d.strftime("%d.%m.%Y") if d else None


def _date_range_label(parsed: ParsedTripDates) -> str:
    if parsed.departure and parsed.return_date:
        return (
            f"{parsed.departure.strftime('%d.%m.%Y')} — "
            f"{parsed.return_date.strftime('%d.%m.%Y')}"
        )
    if parsed.departure:
        return parsed.departure.strftime("%d.%m.%Y")
    return parsed.raw


def _offer(
    *,
    mode: TransportMode,
    provider: str,
    label: str,
    url: str,
    confidence: str = "high",
) -> TicketOffer:
    return TicketOffer(
        mode=mode,
        source=OfferSource.deep_link,
        is_direct=False,
        transfers=0,
        booking_url=url,
        label=label,
        provider=provider,
        confidence=confidence,  # type: ignore[arg-type]
    )


def _avia_aviasales(
    origin: str,
    dest: str,
    origin_iata: str | None,
    dest_iata: str | None,
    dep: date | None,
    ret: date | None,
) -> TicketOffer | None:
    if origin_iata and dest_iata and dep:
        dep_part = dep.strftime("%d%m")
        if ret:
            ret_part = ret.strftime("%d%m")
            path = f"{origin_iata}{dest_iata}{dep_part}{dest_iata}{origin_iata}{ret_part}"
        else:
            path = f"{origin_iata}{dest_iata}{dep_part}"
        url = f"https://www.aviasales.ru/search/{path}"
    else:
        q = urlencode(
            {
                "origin": origin,
                "destination": dest,
                "depart_date": _fmt_iso(dep) or "",
                "return_date": _fmt_iso(ret) or "",
            }
        )
        url = f"https://www.aviasales.ru/?{q}"
    return _offer(
        mode=TransportMode.plane,
        provider="Aviasales",
        label=f"Авиа: {origin} → {dest}",
        url=url,
        confidence="high" if origin_iata and dep else "low",
    )


def _avia_yandex(
    origin: str,
    dest: str,
    dep: date | None,
    ret: date | None,
) -> TicketOffer:
    params: dict[str, str] = {
        "fromName": origin,
        "toName": dest,
    }
    if dep:
        params["when"] = dep.isoformat()
    if ret:
        params["return_date"] = ret.isoformat()
    url = f"https://travel.yandex.ru/avia/search/?{urlencode(params)}"
    return _offer(
        mode=TransportMode.plane,
        provider="Яндекс Путешествия",
        label=f"Авиа (Яндекс): {origin} → {dest}",
        url=url,
    )


def _avia_google(origin: str, dest: str, dep: date | None, ret: date | None) -> TicketOffer:
    parts = [f"Flights from {origin} to {dest}"]
    if dep:
        parts.append(f"on {dep.isoformat()}")
    if ret:
        parts.append(f"returning {ret.isoformat()}")
    q = quote(" ".join(parts))
    url = f"https://www.google.com/travel/flights?q={q}&hl=ru"
    return _offer(
        mode=TransportMode.plane,
        provider="Google Авиабилеты",
        label=f"Авиа (Google): {origin} → {dest}",
        url=url,
    )


def _avia_skyscanner(
    origin_iata: str | None,
    dest_iata: str | None,
    dep: date | None,
    ret: date | None,
    origin: str,
    dest: str,
) -> TicketOffer | None:
    if not (origin_iata and dest_iata and dep):
        return None
    ret_seg = ret.isoformat() if ret else dep.isoformat()
    url = (
        f"https://www.skyscanner.ru/transport/flights/"
        f"{origin_iata.lower()}/{dest_iata.lower()}/{dep.isoformat()}/{ret_seg}/"
    )
    return _offer(
        mode=TransportMode.plane,
        provider="Skyscanner",
        label=f"Авиа (Skyscanner): {origin} → {dest}",
        url=url,
    )


def _train_rzd(origin: str, dest: str, dep: date | None, ret: date | None) -> TicketOffer:
    params: dict[str, str] = {
        "layer_id": "5763",
        "dir": "0",
        "from": origin,
        "to": dest,
    }
    if dep:
        params["date"] = _fmt_rzd(dep) or ""
    url = f"https://ticket.rzd.ru/search/results?{urlencode(params)}"
    label = f"Поезд (РЖД): {origin} → {dest}"
    if ret:
        label += f", обратно {_fmt_rzd(ret)}"
    return _offer(mode=TransportMode.train, provider="РЖД", label=label, url=url)


def _train_tutu(origin: str, dest: str, dep: date | None) -> TicketOffer:
    slug_o, slug_d = _slug(origin), _slug(dest)
    base = f"https://www.tutu.ru/poezda/{slug_o}/{slug_d}/"
    if dep:
        url = f"{base}?date={dep.isoformat()}"
    else:
        url = base
    return _offer(
        mode=TransportMode.train,
        provider="Tutu.ru",
        label=f"Поезд (Tutu): {origin} → {dest}",
        url=url,
    )


def _bus_tutu(origin: str, dest: str, dep: date | None) -> TicketOffer:
    slug_o, slug_d = _slug(origin), _slug(dest)
    base = f"https://bus.tutu.ru/raspisanie/{slug_o}/{slug_d}/"
    url = f"{base}?date={dep.isoformat()}" if dep else base
    return _offer(
        mode=TransportMode.bus,
        provider="Bus.tutu.ru",
        label=f"Автобус (Tutu): {origin} → {dest}",
        url=url,
    )


def _bus_etraffic(origin: str, dest: str) -> TicketOffer:
    q = urlencode({"from": origin, "to": dest})
    return _offer(
        mode=TransportMode.bus,
        provider="E-traffic",
        label=f"Автобус: {origin} → {dest}",
        url=f"https://e-traffic.ru/?{q}",
        confidence="low",
    )


def build_ticket_offers(
    origin_city: str,
    destination_city: str,
    parsed: ParsedTripDates,
) -> list[TicketOffer]:
    """Собирает deep links для самолёта, поезда и автобуса."""
    dep = parsed.departure
    ret = parsed.return_date
    origin_iata = city_to_iata(origin_city)
    dest_iata = city_to_iata(destination_city)
    offers: list[TicketOffer] = []

    avia = _avia_aviasales(
        origin_city, destination_city, origin_iata, dest_iata, dep, ret
    )
    if avia:
        offers.append(avia)
    offers.append(_avia_yandex(origin_city, destination_city, dep, ret))
    offers.append(_avia_google(origin_city, destination_city, dep, ret))
    sky = _avia_skyscanner(origin_iata, dest_iata, dep, ret, origin_city, destination_city)
    if sky:
        offers.append(sky)

    offers.append(_train_rzd(origin_city, destination_city, dep, ret))
    offers.append(_train_tutu(origin_city, destination_city, dep))
    offers.append(_bus_tutu(origin_city, destination_city, dep))
    offers.append(_bus_etraffic(origin_city, destination_city))

    return offers


def format_offers_summary(
    origin_city: str,
    destination_city: str,
    parsed: ParsedTripDates,
    offers: list[TicketOffer],
) -> str:
    """Краткий markdown для LLM из структурированных offers."""
    lines = [
        f"Маршрут: {origin_city} → {destination_city}, даты: {_date_range_label(parsed)}.",
        "Прямых рейсов может не быть — на агрегаторах смотрите варианты со стыковками.",
        "",
    ]
    by_mode: dict[TransportMode, list[TicketOffer]] = {}
    for offer in offers:
        by_mode.setdefault(offer.mode, []).append(offer)

    titles = {
        TransportMode.plane: "Самолёт",
        TransportMode.train: "Поезд",
        TransportMode.bus: "Автобус",
    }
    for mode, title in titles.items():
        block = by_mode.get(mode, [])
        if not block:
            continue
        lines.append(f"**{title}**:")
        for item in block:
            lines.append(f"- {item.label}: {item.booking_url}")
        lines.append("")
    return "\n".join(lines).strip()
