"""Контекст поиска текущей сессии (предпочтения из опросника)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from onboarding.preferences import TripPreferences

_search_context: str = ""
_session_preferences: TripPreferences | None = None


def set_session(preferences: TripPreferences, search_context: str) -> None:
    """Устанавливает предпочтения и строку для enrich_query."""
    global _search_context, _session_preferences
    _session_preferences = preferences
    _search_context = search_context.strip()


def set_search_context(context: str) -> None:
    """Только строка контекста (продолжение поездки без нового опросника)."""
    global _search_context
    _search_context = context.strip()


def get_search_context() -> str:
    return _search_context


def get_session_preferences() -> TripPreferences | None:
    return _session_preferences


def clear_search_context() -> None:
    global _search_context, _session_preferences
    _search_context = ""
    _session_preferences = None


def enrich_query(query: str) -> str:
    """Добавляет предпочтения к поисковому запросу, если заданы."""
    ctx = _search_context
    if not ctx:
        return query
    suffix = ctx[:120]
    return f"{query} {suffix}"
