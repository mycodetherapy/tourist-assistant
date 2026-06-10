"""Состав группы → число пассажиров для deep links и Aviasales."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

TravelParty = Literal[
    "solo",
    "couple",
    "family",
    "friends",
    "parent_child",
    "family_two",
]


@dataclass(frozen=True)
class TicketPassengers:
    adults: int
    children: int = 0
    infants: int = 0

    @property
    def seats(self) -> int:
        """Места в поезде/автобусе и adults+children для авиа."""
        return self.adults + self.children

    def summary_ru(self) -> str:
        parts: list[str] = []
        if self.adults:
            parts.append(f"{self.adults} взр.")
        if self.children:
            parts.append(f"{self.children} реб.")
        if self.infants:
            parts.append(f"{self.infants} млад.")
        return ", ".join(parts) if parts else "1 взр."


def passengers_for_travel_party(party: str) -> TicketPassengers:
    """Маппинг travel_party из опросника на параметры агрегаторов."""
    key = (party or "couple").strip().lower()
    if key == "solo":
        return TicketPassengers(adults=1)
    if key == "couple":
        return TicketPassengers(adults=2)
    if key == "family":
        return TicketPassengers(adults=2, children=1)
    if key == "parent_child":
        return TicketPassengers(adults=1, children=1)
    if key == "family_two":
        return TicketPassengers(adults=2, children=2)
    if key == "friends":
        return TicketPassengers(adults=3)
    return TicketPassengers(adults=2)
