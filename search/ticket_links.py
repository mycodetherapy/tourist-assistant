"""Deep links на агрегаторы билетов с датами и маршрутом."""

from __future__ import annotations

import re
from datetime import date
from urllib.parse import urlencode

from models.tickets import (
    OfferSource,
    ParsedTripDates,
    TicketOffer,
    TransportMode,
)
from search.aviasales_urls import build_aviasales_search_url
from search.airport_routing import (
    AviaEndpoint,
    avia_route_endpoints,
)
from search.ticket_passengers import TicketPassengers, passengers_for_travel_party
from search.transport_codes import (
    bus_ticket_required,
    city_to_rzd_code,
    city_to_tutu_bus,
    city_to_tutu_train_name,
    ground_transport_available,
)

def _avia_summary_link_label(origin: str, dest: str) -> str:
    return f"Aviasales: {origin} → {dest}"

# Старый формат «label: https://…» или «- label: https://…» → markdown-ссылка.
_PLAIN_URL_LINE = re.compile(
    r"^(?P<prefix>(?:\*\*[^*]+\*\*|(?:Самолёт|Поезд|Автобус)):\s*)?"
    r"(?P<bullet>-\s*)?"
    r"(?P<label>.+):\s+(?P<url>https?://\S+)\s*$"
)


def normalize_tickets_markdown(text: str) -> str:
    """Приводит билеты к [label](url) и вертикальному списку рейсов."""
    if not text.strip():
        return text
    out: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("·"):
            out.append(f"- {stripped[1:].strip()}")
            continue
        if " · " in line and not stripped.startswith("-"):
            out.extend(_expand_inline_dot_items(line))
            continue
        if "](http" in line and ": https://" not in line:
            out.append(line)
            continue
        m = _PLAIN_URL_LINE.match(stripped)
        if not m:
            out.append(line)
            continue
        prefix = m.group("prefix") or ""
        bullet = m.group("bullet") or ""
        label = m.group("label").strip()
        url = m.group("url")
        out.append(f"{prefix}{bullet}[{label}]({url})")
    return "\n".join(out)


def _expand_inline_dot_items(line: str) -> list[str]:
    """Строка «ссылка · рейс · рейс» → заголовок + маркированный список."""
    parts = [p.strip() for p in line.split(" · ") if p.strip()]
    if len(parts) <= 1:
        return [line]
    rows = [parts[0], ""]
    rows.extend(f"- {part}" for part in parts[1:])
    return rows


def _travelers_count(passengers: TicketPassengers) -> str:
    return str(max(1, passengers.seats))


def _fmt_tutu_date(d: date) -> str:
    return d.strftime("%d.%m.%Y")


def _fmt_rzd_path_date(d: date) -> str:
    """2026-6-18 без ведущих нулей у месяца/дня."""
    return f"{d.year}-{d.month}-{d.day}"


def _date_range_label(parsed: ParsedTripDates) -> str:
    if parsed.departure and parsed.return_date:
        return (
            f"{parsed.departure.strftime('%d.%m.%Y')} — "
            f"{parsed.return_date.strftime('%d.%m.%Y')}"
        )
    if parsed.departure:
        return parsed.departure.strftime("%d.%m.%Y")
    return parsed.raw


def _route_pax_label(origin: str, dest: str, passengers: TicketPassengers) -> str:
    pax_hint = f" ({passengers.summary_ru()})" if passengers.seats > 1 else ""
    return f"{origin} → {dest}{pax_hint}"


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
    origin_ep: AviaEndpoint | None,
    dest_ep: AviaEndpoint | None,
    dep: date | None,
    ret: date | None,
    passengers: TicketPassengers,
) -> TicketOffer | None:
    if not (origin_ep and dest_ep and dep):
        return None
    url = build_aviasales_search_url(
        origin_ep.iata, dest_ep.iata, dep, ret, passengers=passengers
    )
    route = _route_pax_label(origin, dest, passengers)
    hints: list[str] = []
    if origin_ep.redirected:
        hints.append(f"вылет: аэропорт {origin_ep.hub_label}")
    if dest_ep.redirected:
        hints.append(f"прилёт: аэропорт {dest_ep.hub_label}")
    hint_suffix = f" [{'; '.join(hints)}]" if hints else ""
    return _offer(
        mode=TransportMode.plane,
        provider="Aviasales",
        label=f"Aviasales: {route}{hint_suffix}",
        url=url,
        confidence="high",
    )


def _train_rzd(
    origin: str,
    dest: str,
    dep: date | None,
    passengers: TicketPassengers,
) -> TicketOffer | None:
    from_code = city_to_rzd_code(origin)
    to_code = city_to_rzd_code(dest)
    if not (from_code and to_code and dep):
        return None
    travelers = _travelers_count(passengers)
    path_date = _fmt_rzd_path_date(dep)
    url = (
        f"https://ticket.rzd.ru/searchresults/v/1/"
        f"{from_code}/{to_code}/{path_date}?adult={travelers}"
    )
    pax_hint = f", {passengers.summary_ru()}" if passengers.seats > 1 else ""
    return _offer(
        mode=TransportMode.train,
        provider="РЖД",
        label=f"РЖД: {origin} → {dest}, {_fmt_tutu_date(dep)}{pax_hint}",
        url=url,
    )


def _train_tutu(
    origin: str,
    dest: str,
    dep: date | None,
    passengers: TicketPassengers,
) -> TicketOffer | None:
    name_o = city_to_tutu_train_name(origin)
    name_d = city_to_tutu_train_name(dest)
    if not (name_o and name_d):
        return None
    travelers = _travelers_count(passengers)
    params: dict[str, str] = {"travelers": travelers}
    if dep:
        params["date"] = _fmt_tutu_date(dep)
    url = f"https://www.tutu.ru/poezda/{name_o}/{name_d}/?{urlencode(params)}"
    pax_hint = f" ({passengers.summary_ru()})" if passengers.seats > 1 else ""
    return _offer(
        mode=TransportMode.train,
        provider="Tutu.ru",
        label=f"Tutu (жд): {origin} → {dest}{pax_hint}",
        url=url,
        confidence="high" if dep else "low",
    )


def _bus_tutu(
    origin: str,
    dest: str,
    dep: date | None,
    passengers: TicketPassengers,
) -> TicketOffer | None:
    """Автобус Tutu, в одну сторону (дата вылета)."""
    bus_o = city_to_tutu_bus(origin)
    bus_d = city_to_tutu_bus(dest)
    if not (bus_o and bus_d and dep):
        return None
    gorod_o, from_id = bus_o
    gorod_d, to_id = bus_d
    travelers = _travelers_count(passengers)
    params = {
        "date": _fmt_tutu_date(dep),
        "amount": travelers,
        "from": from_id,
        "to": to_id,
        "travelers": travelers,
    }
    url = (
        f"https://bus.tutu.ru/raspisanie/{gorod_o}/{gorod_d}/"
        f"?{urlencode(params)}"
    )
    return _offer(
        mode=TransportMode.bus,
        provider="Bus.tutu.ru",
        label=f"Tutu (автобус): {origin} → {dest}, {_fmt_tutu_date(dep)}",
        url=url,
    )


def build_ticket_offers(
    origin_city: str,
    destination_city: str,
    parsed: ParsedTripDates,
    *,
    travel_party: str = "couple",
) -> list[TicketOffer]:
    """Собирает deep links: Aviasales, РЖД, Tutu жд, Tutu автобус."""
    dep = parsed.departure
    ret = parsed.return_date
    passengers = passengers_for_travel_party(travel_party)
    origin_ep, dest_ep = avia_route_endpoints(origin_city, destination_city)
    offers: list[TicketOffer] = []

    avia = _avia_aviasales(
        origin_city, destination_city, origin_ep, dest_ep, dep, ret, passengers
    )
    if avia:
        offers.append(avia)

    if ground_transport_available(origin_city, destination_city):
        rzd = _train_rzd(origin_city, destination_city, dep, passengers)
        if rzd:
            offers.append(rzd)
        tutu_train = _train_tutu(origin_city, destination_city, dep, passengers)
        if tutu_train:
            offers.append(tutu_train)

    if bus_ticket_required(origin_city, destination_city):
        bus = _bus_tutu(origin_city, destination_city, dep, passengers)
        if bus:
            offers.append(bus)

    return offers


def format_offers_summary(
    origin_city: str,
    destination_city: str,
    parsed: ParsedTripDates,
    offers: list[TicketOffer],
    *,
    passengers: TicketPassengers | None = None,
) -> str:
    """Краткий markdown для LLM и UI: заголовок блока и кликабельная ссылка."""
    pax = passengers or TicketPassengers(adults=1)
    lines = [
        f"Маршрут: {origin_city} → {destination_city}, даты: {_date_range_label(parsed)}.",
        f"Пассажиры в ссылках: {pax.summary_ru()}",
        "Прямых рейсов может не быть — на Aviasales смотрите варианты со стыковками.",
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
        api_items = [i for i in block if i.source.value == "api"]
        other_items = [i for i in block if i.source.value != "api"]
        lines.append(f"**{title}:**")
        if api_items:
            lines.append(
                f"[{_avia_summary_link_label(origin_city, destination_city)}]"
                f"({api_items[0].booking_url})"
            )
            for item in api_items:
                lines.append(f"- {item.label}")
        elif len(other_items) == 1:
            item = other_items[0]
            lines.append(f"[{item.label}]({item.booking_url})")
        else:
            for item in other_items:
                lines.append(f"- [{item.label}]({item.booking_url})")
        lines.append("")
    return "\n".join(lines).strip()
