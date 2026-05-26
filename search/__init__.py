"""Вспомогательные функции веб-поиска."""

from search.context import (
    clear_search_context,
    enrich_query,
    get_search_context,
    get_session_preferences,
    set_search_context,
    set_session,
)

__all__ = [
    "clear_search_context",
    "enrich_query",
    "get_search_context",
    "get_session_preferences",
    "set_search_context",
    "set_session",
]
