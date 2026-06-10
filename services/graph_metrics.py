"""Per-node и per-tool метрики одного прогона LangGraph."""

from __future__ import annotations

from collections import defaultdict
from contextvars import ContextVar, Token
from time import perf_counter
from typing import Any


class GraphRunMetrics:
    """Собирает длительности узлов графа и вызовов tools за один run."""

    def __init__(self) -> None:
        self._node_totals: dict[str, float] = defaultdict(float)
        self._node_counts: dict[str, int] = defaultdict(int)
        self._timeline: list[dict[str, Any]] = []
        self._tool_totals: dict[str, float] = defaultdict(float)
        self._tool_counts: dict[str, int] = defaultdict(int)
        self._step = 0

    def record_node(self, node: str, duration_sec: float, *, cumulative_sec: float) -> None:
        self._step += 1
        duration_ms = max(0, int(round(duration_sec * 1000)))
        self._node_totals[node] += duration_sec
        self._node_counts[node] += 1
        self._timeline.append(
            {
                "step": self._step,
                "node": node,
                "duration_ms": duration_ms,
                "cumulative_ms": max(0, int(round(cumulative_sec * 1000))),
            }
        )

    def record_tool(self, tool_name: str, duration_sec: float) -> None:
        self._tool_totals[tool_name] += duration_sec
        self._tool_counts[tool_name] += 1

    def to_dict(self) -> dict[str, Any]:
        nodes = {
            name: {
                "count": self._node_counts[name],
                "total_ms": max(0, int(round(total * 1000))),
            }
            for name, total in sorted(
                self._node_totals.items(), key=lambda item: -item[1]
            )
        }
        tools = {
            name: {
                "count": self._tool_counts[name],
                "total_ms": max(0, int(round(total * 1000))),
            }
            for name, total in sorted(
                self._tool_totals.items(), key=lambda item: -item[1]
            )
        }
        payload: dict[str, Any] = {"nodes": nodes, "timeline": self._timeline}
        if tools:
            payload["tools"] = tools
        return payload


_metrics_ctx: ContextVar[GraphRunMetrics | None] = ContextVar("graph_run_metrics", default=None)


def activate_graph_metrics() -> tuple[GraphRunMetrics, Token]:
    """Включает сбор tool-метрик в executor на время прогона."""
    metrics = GraphRunMetrics()
    token = _metrics_ctx.set(metrics)
    return metrics, token


def deactivate_graph_metrics(token: Token) -> None:
    _metrics_ctx.reset(token)


def record_tool_timing(tool_name: str, duration_sec: float) -> None:
    metrics = _metrics_ctx.get()
    if metrics is not None:
        metrics.record_tool(tool_name, duration_sec)


def stream_graph_with_metrics(
    run_state: dict[str, Any],
    config: dict[str, Any],
) -> tuple[dict[str, Any], GraphRunMetrics]:
    """Запускает граф через stream; возвращает финальный state и метрики узлов."""
    from agents.graph import app

    metrics, token = activate_graph_metrics()
    started = perf_counter()
    last = started
    result: dict[str, Any] | None = None
    try:
        for mode, chunk in app.stream(
            run_state,
            config=config,
            stream_mode=["updates", "values"],
        ):
            now = perf_counter()
            if mode == "updates" and isinstance(chunk, dict):
                dt = now - last
                cumulative = now - started
                for node_name in chunk:
                    metrics.record_node(node_name, dt, cumulative_sec=cumulative)
                last = now
            elif mode == "values" and isinstance(chunk, dict):
                result = chunk
    finally:
        deactivate_graph_metrics(token)

    if result is None:
        raise RuntimeError("Graph stream did not emit final state")
    return result, metrics
