"""Уровень 2: tool-level проверки по tool_runs."""

from __future__ import annotations

from typing import Any


def check_tools_called(
    runs: list[dict[str, Any]],
    expected_tools: list[str],
) -> list[str]:
    """Все ли ожидаемые tools есть в логе."""
    called = {r["tool_name"] for r in runs}
    issues: list[str] = []
    for name in expected_tools:
        if name not in called:
            issues.append(f"tool не вызван: {name}")
    return issues


def check_live_data(runs: list[dict[str, Any]], min_ok: int = 2) -> list[str]:
    """Сколько tools вернули live_data."""
    ok = sum(1 for r in runs if r.get("live_data"))
    if ok < min_ok:
        return [f"live_data только у {ok} tools (ожидалось ≥{min_ok})"]
    return []


def check_results_count(runs: list[dict[str, Any]]) -> list[str]:
    issues: list[str] = []
    for row in runs:
        if row.get("live_data") and int(row.get("results_count") or 0) == 0:
            issues.append(f"{row['tool_name']}: results_count=0")
    return issues


def check_tickets_offers(
    runs: list[dict[str, Any]],
    min_offers: int,
) -> list[str]:
    """Минимум offers в search_roundtrip_tickets (deep links + API)."""
    for row in runs:
        if row.get("tool_name") != "search_roundtrip_tickets":
            continue
        count = int(row.get("results_count") or 0)
        if count < min_offers:
            return [
                f"search_roundtrip_tickets: offers={count} (ожидалось ≥{min_offers})"
            ]
        return []
    return ["search_roundtrip_tickets: нет записи в tool_runs"]


def run_tool_checks(
    runs: list[dict[str, Any]],
    expect: dict[str, Any],
) -> list[str]:
    issues = check_tools_called(runs, expect.get("tools", []))
    issues.extend(check_live_data(runs))
    issues.extend(check_results_count(runs))
    min_ticket = expect.get("min_ticket_offers")
    if min_ticket is not None:
        issues.extend(check_tickets_offers(runs, int(min_ticket)))
    return issues
