"""Уровень 1: проверки без LLM."""

from __future__ import annotations

import re
from typing import Any

from pydantic import ValidationError

from models.schemas import FinalProgram, is_legacy_program, normalize_stored_program


def check_program_schema(program: dict[str, Any]) -> list[str]:
    """FinalProgram schema + обязательные секции."""
    issues: list[str] = []
    try:
        model = FinalProgram.model_validate(normalize_stored_program(program))
    except ValidationError as exc:
        return [f"schema: {exc}"]
    if not model.tickets.strip():
        issues.append("пустое поле tickets")
    if not model.lifehacks.strip():
        issues.append("пустое поле lifehacks")
    if is_legacy_program(program):
        if not model.events.strip():
            issues.append("пустое поле events")
        if not model.dining.strip():
            issues.append("пустое поле dining")
    else:
        has_routes = bool(model.routes) or bool(model.routes_text.strip())
        if not has_routes:
            issues.append("пустое поле routes")
    return issues


def check_links_and_markers(
    program: dict[str, Any],
    *,
    min_restaurant_links: int = 6,
    min_route_urls: int = 3,
    tickets_markers: list[str] | None = None,
) -> list[str]:
    issues: list[str] = []
    if is_legacy_program(program):
        dining = str(program.get("dining", ""))
        links = len(re.findall(r"https?://", dining, flags=re.IGNORECASE))
        if links < min_restaurant_links:
            issues.append(f"dining: {links} ссылок (ожидалось ≥{min_restaurant_links})")
    else:
        routes = program.get("routes")
        url_count = 0
        if isinstance(routes, dict):
            cases = routes.get("cases")
            if isinstance(cases, list):
                url_count = sum(
                    1
                    for case in cases
                    if isinstance(case, dict) and str(case.get("maps_route_url", "")).strip()
                )
        if url_count < min_route_urls:
            issues.append(
                f"routes: {url_count} maps_route_url (ожидалось ≥{min_route_urls})"
            )
    tickets = str(program.get("tickets", ""))
    lower = tickets.lower()
    for marker in tickets_markers or ("самол", "поезд"):
        if str(marker).lower() not in lower:
            issues.append(f"tickets: нет маркера {marker}")
    return issues


def run_deterministic_checks(
    program: dict[str, Any],
    expect: dict[str, Any],
) -> list[str]:
    """Объединяет все детерминированные проверки."""
    issues = check_program_schema(program)
    issues.extend(
        check_links_and_markers(
            program,
            min_restaurant_links=int(expect.get("min_restaurant_links", 6)),
            min_route_urls=int(expect.get("min_route_urls", 3)),
            tickets_markers=expect.get("tickets_markers"),
        )
    )
    return issues
