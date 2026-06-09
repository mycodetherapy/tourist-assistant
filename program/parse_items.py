"""Разбивает markdown-секции программы на вводный текст и голосуемые пункты."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from models.schemas import is_legacy_program

ProgramSectionKey = Literal["tickets", "routes", "lifehacks", "events", "dining"]
SECTION_KEYS: tuple[ProgramSectionKey, ...] = (
    "tickets",
    "routes",
    "lifehacks",
    "events",
    "dining",
)

VotableSectionKey = Literal["routes", "route_stops", "lifehacks", "events", "dining"]
VOTABLE_SECTIONS: tuple[VotableSectionKey, ...] = (
    "routes",
    "route_stops",
    "lifehacks",
    "events",
    "dining",
)

_NUMBERED_ITEM = re.compile(r"^\d+\.\s+")
_DASH_ITEM = re.compile(r"^-\s+")
_MODE_HEADER = re.compile(r"^\*\*.+\*\*:?\s*$")
_CONTINUATION = re.compile(r"^(\s{2,}|·\s)")
_ROUTE_HEADER = re.compile(r"^##\s+Вариант\s+([ABC]):", re.IGNORECASE)


@dataclass(frozen=True)
class ParsedSection:
    intro: str
    items: tuple[str, ...]


@dataclass(frozen=True)
class ParsedProgram:
    tickets: ParsedSection
    routes: ParsedSection
    route_stops: ParsedSection
    lifehacks: ParsedSection
    events: ParsedSection
    dining: ParsedSection


def _is_continuation(line: str) -> bool:
    return bool(_CONTINUATION.match(line))


def _has_numbered_items(text: str) -> bool:
    return any(_NUMBERED_ITEM.match(line) for line in text.splitlines())


def _split_numbered(text: str) -> ParsedSection:
    lines = text.splitlines()
    intro_lines: list[str] = []
    items: list[str] = []
    current: list[str] = []

    def flush() -> None:
        if current:
            items.append("\n".join(current).strip())
            current.clear()

    for line in lines:
        if _NUMBERED_ITEM.match(line):
            flush()
            current = [line]
        elif current and _is_continuation(line):
            current.append(line)
        elif current:
            current.append(line)
        else:
            intro_lines.append(line)

    flush()
    if not items and text.strip():
        return ParsedSection(intro="", items=(text.strip(),))
    return ParsedSection(intro="\n".join(intro_lines).strip(), items=tuple(items))


def _split_dash(text: str, *, merge_continuations: bool) -> ParsedSection:
    lines = text.splitlines()
    intro_lines: list[str] = []
    items: list[str] = []
    current: list[str] = []

    def flush() -> None:
        if current:
            items.append("\n".join(current).strip())
            current.clear()

    for line in lines:
        if _DASH_ITEM.match(line):
            flush()
            current = [line]
        elif merge_continuations and current and _is_continuation(line):
            current.append(line)
        elif _MODE_HEADER.match(line) and not current:
            intro_lines.append(line)
        elif current:
            current.append(line)
        else:
            intro_lines.append(line)

    flush()
    return ParsedSection(intro="\n".join(intro_lines).strip(), items=tuple(items))


def _split_lines(text: str) -> ParsedSection:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ParsedSection(intro="", items=())
    if len(lines) == 1:
        return ParsedSection(intro="", items=(lines[0],))
    return ParsedSection(intro="", items=tuple(lines))


def _split_paragraph(text: str) -> ParsedSection:
    stripped = text.strip()
    if not stripped:
        return ParsedSection(intro="", items=())
    if _DASH_ITEM.search(stripped):
        return _split_dash(stripped, merge_continuations=False)
    return ParsedSection(intro="", items=(stripped,))


def _format_route_item_block(case: dict[str, Any]) -> str:
    from agents.route_postprocess import public_route_summary, public_route_title

    case_id = case.get("case_id", "?")
    title = public_route_title(str(case.get("title", "")))
    url = str(case.get("maps_route_url", "")).strip()
    stops = case.get("stops")
    leisure: list[dict[str, Any]] = []
    if isinstance(stops, list):
        leisure = [
            stop
            for stop in stops
            if isinstance(stop, dict) and stop.get("kind") == "leisure"
        ]
    if leisure:
        meta = f"{len(leisure)} остановок"
    else:
        meta = public_route_summary(str(case.get("summary", "")).strip())
    block = f"**Вариант {case_id}: {title}** — {meta}"
    if url:
        block += f"\n\n[Открыть маршрут в Яндекс.Картах]({url})"
    for stop in leisure:
        narrative = str(stop.get("narrative", "")).strip()
        if narrative:
            block += f"\n- {narrative}"
    return block.strip()


def _parse_routes_from_structured(program: dict[str, Any]) -> ParsedSection | None:
    routes = program.get("routes")
    if not isinstance(routes, dict):
        return None
    cases = routes.get("cases")
    if not isinstance(cases, list) or not cases:
        return None
    intro = str(program.get("routes_text", "")).split("##")[0].strip()
    items: list[str] = []
    for case in cases:
        if not isinstance(case, dict):
            continue
        items.append(_format_route_item_block(case))
    return ParsedSection(intro=intro, items=tuple(items))


def _parse_routes_from_text(text: str) -> ParsedSection:
    normalized = (text or "").strip()
    if not normalized:
        return ParsedSection(intro="", items=())
    chunks: list[str] = []
    current: list[str] = []
    intro_lines: list[str] = []
    for line in normalized.splitlines():
        if _ROUTE_HEADER.match(line):
            if current:
                chunks.append("\n".join(current).strip())
            current = [line]
        elif current:
            current.append(line)
        else:
            intro_lines.append(line)
    if current:
        chunks.append("\n".join(current).strip())
    if not chunks:
        return ParsedSection(intro=normalized, items=())
    return ParsedSection(intro="\n".join(intro_lines).strip(), items=tuple(chunks))


def parse_section(section: ProgramSectionKey, text: str) -> ParsedSection:
    normalized = (text or "").strip()
    if not normalized:
        return ParsedSection(intro="", items=())

    if section == "tickets":
        return _split_dash(normalized, merge_continuations=True)

    if section == "routes":
        return _parse_routes_from_text(normalized)

    if section == "dining":
        if _has_numbered_items(normalized):
            return _split_numbered(normalized)
        return _split_dash(normalized, merge_continuations=False)

    if section == "lifehacks":
        if _has_numbered_items(normalized):
            return _split_numbered(normalized)
        return _split_paragraph(normalized)

    if _has_numbered_items(normalized):
        return _split_numbered(normalized)
    if _DASH_ITEM.search(normalized):
        return _split_dash(normalized, merge_continuations=False)
    return _split_lines(normalized)


def parse_program_sections(program: dict[str, Any]) -> ParsedProgram:
    from program.route_stops import parse_route_stops

    routes_structured = _parse_routes_from_structured(program)
    routes_text = str(program.get("routes_text", "")).strip()
    if routes_structured:
        routes = routes_structured
    elif routes_text:
        routes = _parse_routes_from_text(routes_text)
    else:
        routes = ParsedSection(intro="", items=())

    empty = ParsedSection(intro="", items=())
    legacy = is_legacy_program(program)
    return ParsedProgram(
        tickets=parse_section("tickets", program.get("tickets", "")),
        routes=routes,
        route_stops=parse_route_stops(program),
        lifehacks=parse_section("lifehacks", program.get("lifehacks", "")),
        events=parse_section("events", program.get("events", "")) if legacy else empty,
        dining=parse_section("dining", program.get("dining", "")) if legacy else empty,
    )
