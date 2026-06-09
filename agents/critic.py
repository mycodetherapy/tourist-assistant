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

    if scope in ("routes", "events", "dining"):
        trip_id = state.get("trip_id")
        if trip_id is not None:
            from search.route_materials_store import load_route_materials_for_trip

            if load_route_materials_for_trip(int(trip_id)) is None:
                issues.append(
                    "нет сохранённого пула POI — выполните полную пересборку программы"
                )

    program = state.get("program")
    if program:
        issues.extend(
            critic_program_issues(
                program,
                scope,
                origin_city=str(state.get("origin_city", "")),
                destination_city=str(state.get("city", "")),
            )
        )

    if issues:
        return False, "; ".join(issues)
    return True, "проверка пройдена"
