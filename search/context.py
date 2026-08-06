"""Контекст поиска текущего прогона (ContextVar — безопасен для worker и параллельных запросов)."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, Iterator

if TYPE_CHECKING:
    from models.state import AgentState
    from onboarding.preferences import TripPreferences

_search_context: ContextVar[str] = ContextVar("search_context", default="")
_session_preferences: ContextVar[TripPreferences | None] = ContextVar(
    "session_preferences", default=None
)
_route_materials: ContextVar[dict[str, Any] | None] = ContextVar(
    "route_materials", default=None
)
_use_city_pack: ContextVar[bool] = ContextVar("use_city_pack", default=True)


def set_poi_source_policy(*, use_city_pack: bool) -> None:
    """Free tier: только Wikidata; city pack — при LLM (byok/platform)."""
    _use_city_pack.set(bool(use_city_pack))


def get_use_city_pack() -> bool:
    return _use_city_pack.get()


def set_session(preferences: TripPreferences, search_context: str) -> None:
    """Устанавливает предпочтения и строку для enrich_query."""
    _session_preferences.set(preferences)
    _search_context.set(search_context.strip())


def get_session_preferences() -> TripPreferences | None:
    return _session_preferences.get()


def set_route_materials(materials: dict[str, Any]) -> None:
    _route_materials.set(dict(materials))


def get_route_materials() -> dict[str, Any] | None:
    return _route_materials.get()


def clear_route_materials() -> None:
    _route_materials.set(None)


def clear_search_context() -> None:
    _search_context.set("")
    _session_preferences.set(None)
    _route_materials.set(None)
    _use_city_pack.set(True)


def bootstrap_from_agent_state(state: AgentState | dict[str, Any]) -> None:
    """Восстанавливает контекст поиска в текущем потоке/worker из AgentState."""
    from onboarding.preferences import build_search_context, normalize_trip_preferences

    prefs = normalize_trip_preferences(dict(state.get("preferences") or {}))
    raw_ctx = str(state.get("search_context") or "").strip()
    ctx = raw_ctx or build_search_context(prefs)
    set_session(prefs, ctx)

    trip_id = state.get("trip_id")
    if trip_id is None:
        return
    from search.route_materials_store import ensure_route_materials_for_trip

    cached = ensure_route_materials_for_trip(
        int(trip_id),
        city=str(state.get("city") or ""),
        dates=str(state.get("dates") or ""),
        base_program=state.get("base_program"),
    )
    if cached is not None:
        set_route_materials(cached.model_dump())


@contextmanager
def search_context_scope(state: AgentState | dict[str, Any] | None = None) -> Iterator[None]:
    """Контекстный менеджер: bootstrap (опционально) и очистка после прогона."""
    if state is not None:
        bootstrap_from_agent_state(state)
    try:
        yield
    finally:
        clear_search_context()


def enrich_query(query: str) -> str:
    """Добавляет предпочтения к поисковому запросу, если заданы."""
    ctx = _search_context.get()
    if not ctx:
        return query
    suffix = ctx[:120]
    return f"{query} {suffix}"
