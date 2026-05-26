"""Уровень 1: проверки без LLM."""

from __future__ import annotations

import re
from typing import Any

from pydantic import ValidationError

from main import FinalProgram


def check_program_schema(program: dict[str, Any]) -> list[str]:
    """FinalProgram schema + обязательные секции."""
    issues: list[str] = []
    try:
        model = FinalProgram.model_validate(program)
    except ValidationError as exc:
        return [f"schema: {exc}"]
    for field in ("tickets", "events", "dining", "transport", "lifehacks"):
        if not getattr(model, field, "").strip():
            issues.append(f"пустое поле {field}")
    return issues


def check_links_and_markers(
    program: dict[str, Any],
    *,
    min_restaurant_links: int = 6,
    tickets_markers: list[str] | None = None,
) -> list[str]:
    issues: list[str] = []
    dining = str(program.get("dining", ""))
    links = len(re.findall(r"https?://", dining, flags=re.IGNORECASE))
    if links < min_restaurant_links:
        issues.append(f"dining: {links} ссылок (ожидалось ≥{min_restaurant_links})")
    tickets = str(program.get("tickets", ""))
    for marker in tickets_markers or ("✈", "🚂", "🚌"):
        if marker not in tickets:
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
            tickets_markers=expect.get("tickets_markers"),
        )
    )
    return issues
