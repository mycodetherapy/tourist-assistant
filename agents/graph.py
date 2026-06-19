"""Сборка и компиляция графа LangGraph."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from agents.nodes import (
    critic_node,
    executor_node,
    finalize_node,
    planner_node,
    route_after_critic,
    route_after_researcher,
    route_entry,
)
from models.state import AgentState


def build_app():
    """Собирает и компилирует граф researcher → executor → writer → critic."""
    workflow = StateGraph(AgentState)

    workflow.add_node("researcher", planner_node)
    workflow.add_node("executor", executor_node)
    workflow.add_node("writer", finalize_node)
    workflow.add_node("critic", critic_node)

    workflow.add_conditional_edges(
        START,
        route_entry,
        {"researcher": "researcher", "writer": "writer"},
    )
    workflow.add_conditional_edges(
        "researcher",
        route_after_researcher,
        {"executor": "executor", "writer": "writer"},
    )
    workflow.add_edge("executor", "researcher")
    workflow.add_edge("writer", "critic")
    workflow.add_conditional_edges(
        "critic",
        route_after_critic,
        {"__end__": END, "researcher": "researcher"},
    )

    return workflow.compile()


app = build_app()

__all__ = ["app", "build_app"]
