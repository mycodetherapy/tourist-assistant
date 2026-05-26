"""Детерминированная проверка программы перед HITL."""

from __future__ import annotations

import re
from typing import Any

from langchain_core.messages import ToolMessage

from planning.rebuild import required_tools_for_scope


def run_critic(state: dict[str, Any]) -> tuple[bool, str]:
    """
    Проверяет: вызваны ли нужные tools, достаточно ли ссылок в dining.
    Возвращает (passed, notes).
    """
    issues: list[str] = []
    scope = state.get("rebuild_scope", "full")
    required = required_tools_for_scope(scope)

    tools_done: set[str] = set()
    for message in state.get("messages", []):
        if isinstance(message, ToolMessage) and message.name:
            tools_done.add(message.name)

    for tool_name in required:
        if tool_name not in tools_done:
            issues.append(f"не вызван {tool_name}")

    program = state.get("program")
    if program and scope in ("full", "dining"):
        dining = str(program.get("dining", ""))
        link_count = len(re.findall(r"https?://", dining, flags=re.IGNORECASE))
        if link_count < 6:
            issues.append(f"в питании {link_count} ссылок (нужно ≥6)")

    if program and scope in ("full", "tickets"):
        tickets = str(program.get("tickets", ""))
        for marker in ("✈", "🚂", "🚌"):
            if marker not in tickets:
                issues.append(f"в билетах нет {marker}")

    if issues:
        return False, "; ".join(issues)
    return True, "проверка пройдена"
