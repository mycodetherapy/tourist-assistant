"""Детерминированная проверка текстовых секций программы (без LLM)."""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from langchain_core.messages import ToolMessage

from planning.rebuild import resolve_tool_name

_GARBAGE_PREFIX = re.compile(r"^[\s:{}\[\],]+$")
_JSON_ARTIFACT = re.compile(r"^[\s]*[:,\[\]{}]+")

_MIN_LEN = {
    "events": 50,
    "dining": 100,
    "lifehacks": 30,
}

_MIN_LINKS = {
    "events": 2,
    "dining": 6,
}

_DINING_TOOL_NAMES = frozenset({"search_dining", "search_dining_and_transport"})


def is_garbage_section(text: str, section: str) -> bool:
    """
    Обломки structured output (:[]{), пустой текст или секция без смысла.
    Для tickets используйте также finalize_helpers._is_garbage_tickets.
    """
    t = (text or "").strip()
    if len(t) < _MIN_LEN.get(section, 40):
        return True
    head = t[:24]
    if _GARBAGE_PREFIX.match(head) or _JSON_ARTIFACT.match(head):
        return True
    if head.startswith(":[]") or head.startswith(":{") or head.startswith("{") and "http" not in t[:200]:
        return True
    if section == "events":
        low = t.lower()
        has_link = "http" in low
        has_topic = any(w in low for w in ("муз", "выстав", "театр", "афиш", "галере", "достоприм"))
        if not has_link and not has_topic:
            return True
    if section in ("events", "dining") and "http" not in t.lower():
        return True
    if section == "lifehacks":
        from agents.lifehacks_quality import is_garbage_lifehacks

        return is_garbage_lifehacks(t)
    return False


def _count_links(text: str) -> int:
    return len(re.findall(r"https?://", text, flags=re.IGNORECASE))


def issues_for_section(program: dict[str, Any], section: str) -> list[str]:
    """Замечания critic по одной секции FinalProgram."""
    issues: list[str] = []
    raw = str(program.get(section, "")).strip()
    if not raw:
        issues.append(f"пустой раздел «{section}»")
        return issues
    if is_garbage_section(raw, section):
        issues.append(f"раздел «{section}» похож на обломок JSON (например :[{{)")
        return issues
    min_links = _MIN_LINKS.get(section)
    if min_links is not None:
        count = _count_links(raw)
        if count < min_links:
            issues.append(f"в «{section}» {count} ссылок (нужно ≥{min_links})")
    return issues


def critic_program_issues(program: dict[str, Any], scope: str) -> list[str]:
    """Проверки секций в зависимости от rebuild_scope."""
    issues: list[str] = []
    if scope in ("full", "events"):
        issues.extend(issues_for_section(program, "events"))
    if scope in ("full", "dining"):
        issues.extend(issues_for_section(program, "dining"))
    if scope in ("full", "lifehacks"):
        issues.extend(issues_for_section(program, "lifehacks"))
    if scope in ("full", "tickets"):
        tickets = str(program.get("tickets", ""))
        lower = tickets.lower()
        for label in ("самол", "поезд", "автобус"):
            if label not in lower:
                issues.append(f"в билетах нет «{label}…»")
        try:
            from agents.finalize_helpers import _is_garbage_tickets

            if _is_garbage_tickets(tickets):
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
    """Берёт digest из последнего успешного ToolMessage."""
    for msg in reversed(messages):
        if not isinstance(msg, ToolMessage):
            continue
        name = msg.name or ""
        if tool_name in _DINING_TOOL_NAMES:
            if name not in _DINING_TOOL_NAMES:
                continue
        elif name != tool_name:
            continue
        raw = msg.content if isinstance(msg.content, str) else str(msg.content)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if data.get("error"):
            continue
        if resolve_tool_name(name) == "search_culture_events":
            from search.digest_format import format_events_digest

            search_block = data.get("search")
            if isinstance(search_block, dict):
                results = search_block.get("results")
                if isinstance(results, list) and results:
                    return format_events_digest(results)
        digest = str(data.get(digest_key) or data.get("digest") or "").strip()
        if digest:
            if resolve_tool_name(name) == "search_culture_events":
                from search.digest_format import clean_events_display

                return clean_events_display(digest)
            return digest
    return None


def resolve_text_section(
    section: str,
    llm_value: str,
    *,
    messages: list[Any],
    base_program: Optional[dict[str, Any]],
    tool_name: str | None,
    digest_key: str = "digest",
    city: str = "",
    search_context: str = "",
    walking_area: str = "",
) -> str:
    """
    Приоритет: валидный LLM-текст → digest из tool → сохранённая программа → заглушка.
    """
    value = (llm_value or "").strip()
    if section == "events":
        from search.digest_format import clean_events_display

        value = clean_events_display(value)
    if section == "lifehacks":
        from agents.lifehacks_quality import clean_lifehacks_display

        value = clean_lifehacks_display(
            value,
            city=city,
            walking_area=walking_area or search_context,
            search_context=search_context,
        )
    if value and not is_garbage_section(value, section):
        return value

    if tool_name:
        from_tool = extract_tool_digest(messages, tool_name, digest_key=digest_key)
        if from_tool and not is_garbage_section(from_tool, section):
            return from_tool

    if base_program:
        base_val = str(base_program.get(section, "")).strip()
        if section == "lifehacks":
            from agents.lifehacks_quality import clean_lifehacks_display

            base_val = clean_lifehacks_display(
                base_val,
                city=city,
                walking_area=walking_area or search_context,
                search_context=search_context,
            )
        if base_val and not is_garbage_section(base_val, section):
            return base_val

    labels = {
        "events": "Мероприятия",
        "dining": "Питание",
        "lifehacks": "Лайфхаки",
    }
    label = labels.get(section, section)
    tool_hint = f" ({tool_name})" if tool_name else ""
    return (
        f"{label}: не удалось собрать раздел{tool_hint}. "
        "Повторите пересбор или полный прогон."
    )
