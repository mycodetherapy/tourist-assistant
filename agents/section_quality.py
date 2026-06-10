"""Детерминированная проверка текстовых секций программы (без LLM)."""

from __future__ import annotations

import re
from typing import Any

from agents.route_postprocess import (
    CRITIC_ROUTE_PAIR_LIMITS,
    _profile_for_case_id,
    leisure_overlap_ratio,
    overlap_limits_for_pool,
)
from models.routes import RouteProgram, TripRouteCase
from search.transport_codes import required_ticket_markers

_GARBAGE_PREFIX = re.compile(r"^[\s:{}\[\],]+$")
_JSON_ARTIFACT = re.compile(r"^[\s]*[:,\[\]{}]+")

_MIN_LEN = {
    "routes_text": 80,
    "lifehacks": 30,
    "events": 50,
    "dining": 100,
}


def is_garbage_section(text: str, section: str) -> bool:
    t = (text or "").strip()
    if section == "routes_text":
        return len(t) < _MIN_LEN.get("routes_text", 80)
    if len(t) < _MIN_LEN.get(section, 40):
        return True
    head = t[:24]
    if _GARBAGE_PREFIX.match(head) or _JSON_ARTIFACT.match(head):
        return True
    if head.startswith(":[]") or head.startswith(":{") or head.startswith("{") and "http" not in t[:200]:
        return True
    if section == "lifehacks":
        from agents.lifehacks_quality import is_garbage_lifehacks

        return is_garbage_lifehacks(t)
    if section in ("events", "dining") and "http" not in t.lower():
        return True
    return False


def _min_leisure_for_case(case_id: str) -> int:
    key = case_id[2:] if case_id.startswith("N-") else case_id
    return {"A": 3, "B": 3, "C": 3}.get(key, 2)


def _routes_issues(program: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    raw = program.get("routes")
    text = str(program.get("routes_text", "")).strip()
    if not raw and not text:
        issues.append("пустой раздел «routes»")
        return issues
    try:
        routes = RouteProgram.model_validate(raw) if isinstance(raw, dict) else None
    except Exception:
        issues.append("некорректный JSON routes")
        return issues
    if routes is None:
        issues.append("отсутствует структура routes")
        return issues
    preserved = [c for c in routes.cases if c.preserved]
    new_cases = [c for c in routes.cases if not c.preserved]
    if preserved:
        if len(new_cases) < 3:
            issues.append(
                f"после пересборки нужно 3 новых маршрута, получено {len(new_cases)}"
            )
    else:
        if len(routes.cases) != 3:
            issues.append(f"в routes {len(routes.cases)} вариантов (нужно 3)")
        ids = {"A", "B", "C"}
        found = {c.case_id for c in routes.cases}
        if found != ids:
            issues.append(f"ожидались case_id A/B/C, получено {sorted(found)}")
    for case in routes.cases:
        leisure = sum(1 for s in case.stops if s.kind == "leisure")
        need = _min_leisure_for_case(case.case_id)
        if leisure < need:
            issues.append(f"вариант {case.case_id}: {leisure} leisure (нужно ≥{need})")
        if not case.maps_route_url:
            issues.append(f"вариант {case.case_id}: нет maps_route_url")
    if preserved and new_cases:
        for new_case in new_cases:
            for kept in preserved:
                if leisure_overlap_ratio(new_case, kept) > 0.5:
                    issues.append(
                        f"новый {new_case.case_id} слишком похож на сохранённый {kept.case_id}"
                    )
    elif len(routes.cases) >= 3:
        active = [c for c in routes.cases if not c.preserved]
        if len(active) >= 2:
            pool_guess = max(
                (
                    len({s.poi_id for s in c.stops if s.kind == "leisure" and s.poi_id})
                    for c in active
                ),
                default=0,
            )
            limits = overlap_limits_for_pool(
                max(pool_guess * 2, 8), limits=CRITIC_ROUTE_PAIR_LIMITS
            )
            by_profile: dict[str, TripRouteCase] = {}
            for case in active:
                profile_key = _profile_for_case_id(case.case_id)
                if profile_key in ("A", "B", "C"):
                    by_profile[profile_key] = case
            for left, right in (("A", "B"), ("B", "C"), ("A", "C")):
                a_case = by_profile.get(left)
                b_case = by_profile.get(right)
                if a_case is None or b_case is None:
                    continue
                cap = limits.get((left, right), 0.8)
                ratio = leisure_overlap_ratio(a_case, b_case)
                if ratio >= 1.0:
                    issues.append(
                        f"варианты {left} и {right} совпадают по остановкам"
                    )
                elif ratio > cap:
                    issues.append(
                        f"варианты {left} и {right} слишком похожи "
                        f"({int(ratio * 100)}% общих POI)"
                    )
            urls = [
                str(c.maps_route_url).strip()
                for c in active
                if str(c.maps_route_url).strip()
            ]
            if len(urls) >= 2 and len(urls) != len(set(urls)):
                issues.append("разные варианты ведут на один maps_route_url")
    if text and is_garbage_section(text, "routes_text"):
        issues.append("routes_text похож на обломок JSON")
    return issues


def issues_for_section(program: dict[str, Any], section: str) -> list[str]:
    if section == "routes":
        return _routes_issues(program)
    issues: list[str] = []
    raw = str(program.get(section, "")).strip()
    if not raw:
        issues.append(f"пустой раздел «{section}»")
        return issues
    if is_garbage_section(raw, section):
        issues.append(f"раздел «{section}» похож на обломок JSON")
    return issues


def critic_program_issues(
    program: dict[str, Any],
    scope: str,
    *,
    origin_city: str = "",
    destination_city: str = "",
) -> list[str]:
    issues: list[str] = []
    if scope in ("full", "routes", "events", "dining"):
        if program.get("routes") or program.get("routes_text"):
            issues.extend(_routes_issues(program))
        elif scope in ("full", "events", "dining"):
            issues.extend(issues_for_section(program, "events"))
            issues.extend(issues_for_section(program, "dining"))
    if scope in ("full", "lifehacks"):
        issues.extend(issues_for_section(program, "lifehacks"))
    if scope in ("full", "tickets"):
        tickets = str(program.get("tickets", ""))
        lower = tickets.lower()
        for label in required_ticket_markers(origin_city, destination_city):
            if label not in lower:
                issues.append(f"в билетах нет «{label}…»")
        try:
            from agents.finalize_helpers import _is_garbage_tickets

            if _is_garbage_tickets(
                tickets,
                origin_city=origin_city,
                destination_city=destination_city,
            ):
                issues.append("раздел «tickets» некорректен")
        except ImportError:
            pass
    return issues
