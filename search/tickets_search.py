"""Оркестрация search_roundtrip_tickets (фаза 1: deep links, без API)."""

from __future__ import annotations

from pydantic import ValidationError

from models.tickets import TicketsSearchInput, TicketsSearchOutput
from planning.dates import parse_trip_dates
from search.city_codes import city_to_iata
from search.ticket_links import build_ticket_offers, format_offers_summary

_TICKETS_INSTRUCTION = (
    "Используй ТОЛЬКО поля offers и summary_for_llm из этого JSON. "
    "Раздел tickets в программе: три блока — Самолёт, Поезд, Автобус. "
    "В каждом блоке перечисли ссылки из offers (label + booking_url). "
    "Не подставляй главные страницы агрегаторов без дат. "
    "Цены не выдумывай — на фазе 1 только deep links; напиши «цена на сайте». "
    "Если прямых рейсов нет, укажи что на Aviasales/Яндекс видны стыковки."
)


def run_tickets_search(
    origin_city: str,
    destination_city: str,
    dates: str,
) -> TicketsSearchOutput:
    """Собирает структурированный ответ инструмента билетов."""
    try:
        params = TicketsSearchInput(
            origin_city=origin_city,
            destination_city=destination_city,
            dates=dates,
        )
    except ValidationError as exc:
        return TicketsSearchOutput(
            live_data=False,
            params=TicketsSearchInput(
                origin_city=origin_city or "?",
                destination_city=destination_city or "?",
                dates=dates or "?",
            ),
            parsed_dates=parse_trip_dates(dates or ""),
            error=str(exc),
            instruction=_TICKETS_INSTRUCTION,
        )

    parsed = parse_trip_dates(params.dates)
    warnings: list[str] = []

    if parsed.parse_status == "failed":
        warnings.append(
            "Не удалось разобрать даты — ссылки могут быть без точных дат в URL."
        )
    elif parsed.parse_status == "partial":
        warnings.append(
            "Указана только дата вылета — для обратного билета проверьте дату на сайте."
        )

    origin_iata = city_to_iata(params.origin_city)
    dest_iata = city_to_iata(params.destination_city)
    if not origin_iata or not dest_iata:
        warnings.append(
            "IATA не найден для одного из городов — авиа-ссылки могут быть менее точными."
        )

    offers = build_ticket_offers(
        params.origin_city,
        params.destination_city,
        parsed,
    )
    summary = format_offers_summary(
        params.origin_city,
        params.destination_city,
        parsed,
        offers,
    )

    print(f"  → билеты [deep links]: {len(offers)} ссылок (даты: {parsed.parse_status})")

    return TicketsSearchOutput(
        live_data=len(offers) > 0,
        params=params,
        parsed_dates=parsed,
        origin_iata=origin_iata,
        destination_iata=dest_iata,
        avia_api_status="disabled",
        train_api_status="disabled",
        offers=offers,
        summary_for_llm=summary,
        instruction=_TICKETS_INSTRUCTION,
        warning=" ".join(warnings) if warnings else None,
    )
