"""Разбивает markdown-секции программы на вводный текст и голосуемые пункты."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

ProgramSectionKey = Literal["tickets", "events", "dining", "lifehacks"]
SECTION_KEYS: tuple[ProgramSectionKey, ...] = (
    "tickets",
    "events",
    "dining",
    "lifehacks",
)

VotableSectionKey = Literal["events", "dining", "lifehacks"]
VOTABLE_SECTIONS: tuple[VotableSectionKey, ...] = ("events", "dining", "lifehacks")

_NUMBERED_ITEM = re.compile(r"^\d+\.\s+")
_DASH_ITEM = re.compile(r"^-\s+")
_MODE_HEADER = re.compile(r"^\*\*.+\*\*:?\s*$")
_CONTINUATION = re.compile(r"^(\s{2,}|·\s)")


@dataclass(frozen=True)
class ParsedSection:
    intro: str
    items: tuple[str, ...]


@dataclass(frozen=True)
class ParsedProgram:
    tickets: ParsedSection
    events: ParsedSection
    dining: ParsedSection
    lifehacks: ParsedSection


def _is_continuation(line: str) -> bool:
    return bool(_CONTINUATION.match(line))


def _has_numbered_items(text: str) -> bool:
    """Есть ли строки вида «1. …» (проверка построчно, не только с начала текста)."""
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


def parse_section(section: ProgramSectionKey, text: str) -> ParsedSection:
    """Возвращает вводный блок и список пунктов для голосования."""
    normalized = (text or "").strip()
    if not normalized:
        return ParsedSection(intro="", items=())

    if section == "tickets":
        return _split_dash(normalized, merge_continuations=True)

    if section == "dining":
        if _has_numbered_items(normalized):
            return _split_numbered(normalized)
        return _split_dash(normalized, merge_continuations=False)

    if section == "lifehacks":
        if _has_numbered_items(normalized):
            return _split_numbered(normalized)
        return _split_paragraph(normalized)

    # events
    if _has_numbered_items(normalized):
        return _split_numbered(normalized)
    if _DASH_ITEM.search(normalized):
        return _split_dash(normalized, merge_continuations=False)
    return _split_lines(normalized)


def parse_program_sections(program: dict[str, str]) -> ParsedProgram:
    """Разбирает все четыре секции FinalProgram."""
    return ParsedProgram(
        tickets=parse_section("tickets", program.get("tickets", "")),
        events=parse_section("events", program.get("events", "")),
        dining=parse_section("dining", program.get("dining", "")),
        lifehacks=parse_section("lifehacks", program.get("lifehacks", "")),
    )
