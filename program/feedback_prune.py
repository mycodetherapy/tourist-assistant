"""Сброс устаревших оценок после пересборки программы."""

from __future__ import annotations

from typing import Any

from models.schemas import normalize_stored_program
from program.item_key import make_item_key
from program.parse_items import VOTABLE_SECTIONS, VotableSectionKey, parse_program_sections
from program.route_stops import route_stop_keys_for_program

_SCOPE_AFFECTED: dict[str, tuple[VotableSectionKey, ...]] = {
    "full": VOTABLE_SECTIONS,
    "routes": ("routes", "route_stops"),
    "events": ("routes", "route_stops", "events"),
    "dining": ("routes", "route_stops", "dining"),
    "lifehacks": ("lifehacks",),
    "tickets": (),
}


def affected_votable_sections(scope: str) -> tuple[VotableSectionKey, ...]:
    """Какие голосуемые секции затронуты пересборкой."""
    return _SCOPE_AFFECTED.get(scope, VOTABLE_SECTIONS)


def find_stale_feedback_keys(
    program: dict[str, Any],
    scope: str,
    *,
    existing: list[tuple[str, str]],
    trip_id: int | None = None,
    reset_route_stops: bool = False,
) -> list[tuple[str, str]]:
    """
    Пары (section, item_key) для удаления: пункт пересобран или исчез.

    existing — текущие оценки поездки: [(section, item_key), ...].
    reset_route_stops — после пересборки маршрутов сбросить все оценки остановок.
    """
    affected = affected_votable_sections(scope)
    if not affected or not existing:
        return []

    normalized = normalize_stored_program(program)
    parsed = parse_program_sections(normalized)
    valid_by_section: dict[str, set[str]] = {}
    for section in affected:
        if section == "route_stops":
            if reset_route_stops:
                valid_by_section[section] = set()
            else:
                valid_by_section[section] = route_stop_keys_for_program(normalized)
            continue
        items = getattr(parsed, section).items
        valid_by_section[section] = {
            make_item_key(section, text) for text in items
        }

    stale: list[tuple[str, str]] = []
    for section, item_key in existing:
        if section not in affected:
            continue
        if item_key not in valid_by_section.get(section, set()):
            stale.append((section, item_key))
    return stale
