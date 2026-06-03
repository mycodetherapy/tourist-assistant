"""Pydantic-контракты инструмента search_roundtrip_tickets (фаза 1: deep links)."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator


class TicketsSearchInput(BaseModel):
    """Вход search_roundtrip_tickets (аргументы tool / LLM)."""

    origin_city: str = Field(..., description="Город отправления")
    destination_city: str = Field(..., description="Город назначения")
    dates: str = Field(..., description="Даты поездки в свободной форме")


class ParsedTripDates(BaseModel):
    """Нормализованные даты после parse_trip_dates."""

    departure: Optional[date] = None
    return_date: Optional[date] = None
    raw: str
    parse_status: Literal["ok", "partial", "failed"]


class TransportMode(str, Enum):
    plane = "plane"
    train = "train"
    bus = "bus"


class OfferSource(str, Enum):
    deep_link = "deep_link"
    api = "api"


class TicketSegment(BaseModel):
    """Сегмент маршрута (заполняется API на фазе 2; для deep link пустой)."""

    from_city: str
    to_city: str
    from_code: Optional[str] = None
    to_code: Optional[str] = None
    departure_at: Optional[datetime] = None
    arrival_at: Optional[datetime] = None
    carrier: Optional[str] = None
    number: Optional[str] = None


class TicketOffer(BaseModel):
    """Один вариант покупки / поиска билетов."""

    mode: TransportMode
    source: OfferSource = OfferSource.deep_link
    is_direct: bool = True
    transfers: int = 0
    segments: List[TicketSegment] = Field(default_factory=list)
    price_from: Optional[int] = None
    currency: str = "RUB"
    booking_url: str
    label: str
    confidence: Literal["high", "low"] = "high"
    provider: str = Field(..., description="Aviasales, РЖД, Tutu.ru и т.д.")


class TicketsSearchOutput(BaseModel):
    """Структурированный JSON-ответ search_roundtrip_tickets."""

    schema_version: Literal["1"] = "1"
    live_data: bool = True
    category: Literal["tickets"] = "tickets"
    params: TicketsSearchInput
    parsed_dates: ParsedTripDates
    origin_iata: Optional[str] = None
    destination_iata: Optional[str] = None
    avia_api_status: Literal["disabled", "ok", "empty", "error"] = "disabled"
    train_api_status: Literal["disabled", "ok", "empty", "error"] = "disabled"
    offers: List[TicketOffer] = Field(default_factory=list)
    offers_count: int = 0
    results_count: int = 0
    summary_for_llm: str = ""
    instruction: str = ""
    warning: Optional[str] = None
    error: Optional[str] = None

    @model_validator(mode="after")
    def _sync_counts(self) -> TicketsSearchOutput:
        count = len(self.offers)
        self.offers_count = count
        self.results_count = count
        return self
