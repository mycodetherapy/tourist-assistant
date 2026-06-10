"""Контекст поиска текущей сессии (предпочтения из опросника)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from onboarding.preferences import TripPreferences

_search_context: str = ""
_session_preferences: TripPreferences | None = None
_route_materials: dict[str, Any] | None = None


def set_session(preferences: TripPreferences, search_context: str) -> None:
    """Устанавливает предпочтения и строку для enrich_query."""
    global _search_context, _session_preferences
    _session_preferences = preferences
    _search_context = search_context.strip()


def get_session_preferences() -> TripPreferences | None:
    return _session_preferences


def set_route_materials(materials: dict[str, Any]) -> None:
    global _route_materials
    _route_materials = dict(materials)


def get_route_materials() -> dict[str, Any] | None:
    return _route_materials


def clear_route_materials() -> None:
    global _route_materials
    _route_materials = None


def clear_search_context() -> None:
    global _search_context, _session_preferences, _route_materials
    _search_context = ""
    _session_preferences = None
    _route_materials = None


def enrich_query(query: str) -> str:
    """Добавляет предпочтения к поисковому запросу, если заданы."""
    ctx = _search_context
    if not ctx:
        return query
    suffix = ctx[:120]
    return f"{query} {suffix}"
