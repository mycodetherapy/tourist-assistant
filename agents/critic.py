"""Детерминированная проверка программы перед HITL."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import ToolMessage

from agents.section_quality import critic_program_issues
from planning.rebuild import required_tools_for_scope, tool_call_satisfied


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
        if not tool_call_satisfied(tool_name, tools_done):
            issues.append(f"не вызван {tool_name}")

    program = state.get("program")
    if program:
        issues.extend(critic_program_issues(program, scope))

    if issues:
        return False, "; ".join(issues)
    return True, "проверка пройдена"
