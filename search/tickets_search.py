"""Оркестрация search_roundtrip_tickets: deep links + опционально API авиа."""

from __future__ import annotations

from pydantic import ValidationError

from models.tickets import (
    TicketOffer,
    TicketsSearchInput,
    TicketsSearchOutput,
    TransportMode,
)
from planning.dates import parse_trip_dates
from search.city_codes import city_to_iata
from search.providers.avia import fetch_avia_offers
from search.ticket_links import build_ticket_offers, format_offers_summary
from search.transport_codes import ground_transport_available

_TICKETS_INSTRUCTION_BASE = (
    "Используй ТОЛЬКО поля offers и summary_for_llm из этого JSON. "
    "Раздел tickets: три блока — Самолёт, Поезд, Автобус. "
    "В каждом блоке: label + booking_url из offers. "
    "Не подставляй главные страницы агрегаторов без дат."
)


def _instruction_for(avia_api_status: str) -> str:
    if avia_api_status == "ok":
        return (
            f"{_TICKETS_INSTRUCTION_BASE} "
            "Для самолёта: сначала варианты source=api (цена «от N ₽» только из price_from). "
            "Пересадки — по полю transfers и label. "
            "Доп. ссылки source=deep_link — полная выдача на агрегаторе."
        )
    return (
        f"{_TICKETS_INSTRUCTION_BASE} "
        "Цены по авиа не выдумывай — только deep links, «цена на сайте». "
        "Укажи, что стыковки видны на Aviasales."
    )


def _merge_offers(
    api_plane: list[TicketOffer],
    deep_offers: list[TicketOffer],
) -> list[TicketOffer]:
    """API-варианты первыми; без дубля Aviasales deep link при успешном API."""
    if not api_plane:
        return deep_offers
    non_plane = [o for o in deep_offers if o.mode != TransportMode.plane]
    plane_deep = [
        o
        for o in deep_offers
        if o.mode == TransportMode.plane and o.provider != "Aviasales"
    ]
    return api_plane + plane_deep + non_plane


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
            instruction=_instruction_for("disabled"),
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
            "IATA не найден для одного из городов — авиа-API и часть ссылок недоступны."
        )

    avia_api_status = "disabled"
    api_plane: list[TicketOffer] = []
    if origin_iata and dest_iata and parsed.departure:
        api_plane, avia_api_status = fetch_avia_offers(
            origin_iata, dest_iata, parsed
        )
    elif origin_iata and dest_iata:
        avia_api_status = "empty"

    deep_offers = build_ticket_offers(
        params.origin_city,
        params.destination_city,
        parsed,
    )
    offers = _merge_offers(api_plane, deep_offers)

    if avia_api_status == "ok" and not any(o.is_direct for o in api_plane):
        warnings.append(
            "Прямых рейсов в API нет — в блоке «Самолёт» укажи варианты с пересадками "
            "и дай ссылки deep_link для полной выдачи."
        )
    elif avia_api_status == "empty" and origin_iata and dest_iata:
        warnings.append(
            "API авиа не вернул вариантов — используйте deep links; возможны стыковки на сайте."
        )
    elif avia_api_status == "error":
        warnings.append("API авиа недоступен — только deep links.")

    summary = format_offers_summary(
        params.origin_city,
        params.destination_city,
        parsed,
        offers,
    )

    instruction = _instruction_for(avia_api_status)
    if not ground_transport_available(params.origin_city, params.destination_city):
        instruction += (
            " Для зарубежного маршрута жд и автобус недоступны — "
            "в разделе tickets только блок «Самолёт»."
        )

    providers = ["deep_links"]
    if avia_api_status == "ok":
        providers.append("travelpayouts")
    print(
        f"  → билеты: {len(offers)} offers "
        f"(даты: {parsed.parse_status}, avia_api: {avia_api_status})"
    )

    return TicketsSearchOutput(
        live_data=len(offers) > 0,
        params=params,
        parsed_dates=parsed,
        origin_iata=origin_iata,
        destination_iata=dest_iata,
        avia_api_status=avia_api_status,
        train_api_status="disabled",
        offers=offers,
        summary_for_llm=summary,
        instruction=instruction,
        warning=" ".join(warnings) if warnings else None,
    )
