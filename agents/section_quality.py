"""Детерминированная проверка текстовых секций программы (без LLM)."""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from langchain_core.messages import ToolMessage

from agents.route_postprocess import leisure_overlap_ratio
from models.routes import RouteProgram
from planning.rebuild import resolve_tool_name
from search.transport_codes import ground_transport_available

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
    if len(routes.cases) != 3:
        issues.append(f"в routes {len(routes.cases)} вариантов (нужно 3)")
    ids = {"A", "B", "C"}
    found = {c.case_id for c in routes.cases}
    if found != ids:
        issues.append(f"ожидались case_id A/B/C, получено {sorted(found)}")
    for case in routes.cases:
        leisure = sum(1 for s in case.stops if s.kind == "leisure")
        dining = sum(1 for s in case.stops if s.kind == "dining")
        if leisure < 3:
            issues.append(f"вариант {case.case_id}: {leisure} leisure (нужно ≥3)")
        if dining < 2:
            issues.append(f"вариант {case.case_id}: {dining} dining (нужно ≥2)")
        if not case.maps_route_url:
            issues.append(f"вариант {case.case_id}: нет maps_route_url")
    if len(routes.cases) >= 2:
        if leisure_overlap_ratio(routes.cases[0], routes.cases[1]) > 0.85:
            issues.append("варианты A и B слишком похожи")
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
        required_blocks = ["самол"]
        if ground_transport_available(origin_city, destination_city):
            required_blocks.extend(["поезд", "автобус"])
        for label in required_blocks:
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


def extract_tool_digest(
    messages: list[Any],
    tool_name: str,
    *,
    digest_key: str = "digest",
) -> Optional[str]:
    for msg in reversed(messages):
        if not isinstance(msg, ToolMessage):
            continue
        name = msg.name or ""
        if resolve_tool_name(name) != resolve_tool_name(tool_name):
            continue
        raw = msg.content if isinstance(msg.content, str) else str(msg.content)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if data.get("error"):
            continue
        digest = str(
            data.get(digest_key)
            or data.get("materials_digest")
            or data.get("digest")
            or ""
        ).strip()
        if digest:
            return digest
    return None
