"""Состояние графа LangGraph."""

from __future__ import annotations

from typing import Annotated, Any, Literal, TypedDict

ReviewMode = Literal["cli", "deferred"]

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    """Состояние агента: поездка, предпочтения, сообщения, итоговая программа."""

    trip_id: int
    city: str
    dates: str
    origin_city: str
    search_context: str
    preferences: dict[str, Any]
    program: dict[str, Any]
    rebuild_scope: str
    base_program: dict[str, Any]
    critic_passed: bool
    critic_notes: str
    retry_count: int
    approved: bool
    review_mode: ReviewMode
    route_feedback_snapshot: dict[str, Any]
    messages: Annotated[list[AnyMessage], add_messages]
