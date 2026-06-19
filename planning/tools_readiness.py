"""Детерминированная проверка готовности tools перед writer."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import ToolMessage

from planning.rebuild import (
    required_tools_for_scope,
    resolve_tool_name,
    tool_call_satisfied,
)

_FALLBACK_WARNING = (
    "Реальные места не найдены (Wikidata/OSM). Маршруты собраны из запасного набора точек."
)


@dataclass(frozen=True)
class ToolsReadinessResult:
    ready: bool
    warnings: tuple[str, ...] = field(default_factory=tuple)
    reason: str | None = None


def collect_tools_done(messages: list[Any]) -> set[str]:
    done: set[str] = set()
    for message in messages:
        if isinstance(message, ToolMessage) and message.name:
            done.add(message.name)
    return done


def latest_tool_message(messages: list[Any], tool_name: str) -> ToolMessage | None:
    canonical = resolve_tool_name(tool_name)
    for message in reversed(messages):
        if not isinstance(message, ToolMessage) or not message.name:
            continue
        if resolve_tool_name(message.name) == canonical:
            return message
    return None


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    return str(content)


def _collect_payload_warnings(data: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    raw_warnings = data.get("warnings")
    if isinstance(raw_warnings, list):
        warnings.extend(str(item).strip() for item in raw_warnings if str(item).strip())
    raw_warning = data.get("warning")
    if raw_warning and str(raw_warning).strip():
        text = str(raw_warning).strip()
        if text not in warnings:
            warnings.append(text)
    return warnings


def _materials_all_demo(materials: dict[str, Any]) -> bool:
    points = materials.get("leisure_points")
    if not isinstance(points, list) or not points:
        return False
    for point in points:
        if not isinstance(point, dict):
            return False
        maps_url = str(point.get("maps_url") or "")
        if "/org/demo_" not in maps_url:
            return False
    return True


def evaluate_materials_tool(content: str) -> ToolsReadinessResult:
    text = _content_text(content).strip()
    if text.startswith("Ошибка выполнения инструмента"):
        return ToolsReadinessResult(ready=False, reason=text[:200])

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return ToolsReadinessResult(ready=False, reason="invalid tool JSON")

    if not isinstance(data, dict):
        return ToolsReadinessResult(ready=False, reason="invalid tool payload")

    if data.get("error") and data.get("category") != "route_materials":
        return ToolsReadinessResult(ready=False, reason=str(data.get("error"))[:200])

    if "error" in data and not data.get("materials"):
        return ToolsReadinessResult(ready=False, reason=str(data.get("error"))[:200])

    leisure_count = int(data.get("leisure_count", 0) or 0)
    if leisure_count == 0:
        materials = data.get("materials")
        if isinstance(materials, dict):
            leisure_count = len(materials.get("leisure_points") or [])
    if leisure_count == 0:
        return ToolsReadinessResult(ready=False, reason="leisure_count == 0")

    warnings = _collect_payload_warnings(data)
    provider = str(data.get("provider") or "")
    materials = data.get("materials")
    if provider == "fallback" or (
        isinstance(materials, dict) and _materials_all_demo(materials)
    ):
        if _FALLBACK_WARNING not in warnings:
            warnings.insert(0, _FALLBACK_WARNING)

    return ToolsReadinessResult(ready=True, warnings=tuple(warnings))


def evaluate_tools_readiness(state: dict[str, Any]) -> ToolsReadinessResult:
    """Проверяет, можно ли после executor идти в writer без LLM-researcher."""
    scope = str(state.get("rebuild_scope", "full"))
    required = required_tools_for_scope(scope)
    messages = state.get("messages") or []

    if not required:
        return ToolsReadinessResult(ready=True)

    tools_done = collect_tools_done(messages)
    for tool_name in required:
        if not tool_call_satisfied(tool_name, tools_done):
            return ToolsReadinessResult(
                ready=False,
                reason=f"не вызван {tool_name}",
            )

    for tool_name in required:
        msg = latest_tool_message(messages, tool_name)
        if msg is None:
            return ToolsReadinessResult(ready=False, reason=f"нет ToolMessage для {tool_name}")
        if resolve_tool_name(tool_name) == "search_route_materials":
            result = evaluate_materials_tool(_content_text(msg.content))
            if not result.ready:
                return result
            return ToolsReadinessResult(ready=True, warnings=result.warnings)

    return ToolsReadinessResult(ready=True)
