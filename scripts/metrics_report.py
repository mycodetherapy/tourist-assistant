"""Отчёт по метрикам локальных прогонов (SQLite).

Считает:
- latency p50/p95 по duration_ms (agent_runs)
- cost/run (если доступен OpenAI callback)
- per-node p50 по node_timings (если есть)
"""

from __future__ import annotations

import argparse
import math
from collections import defaultdict
from statistics import median
from typing import Any

from db import init_db, list_agent_runs


def _percentile(values: list[int], p: float) -> int:
    if not values:
        return 0
    values_sorted = sorted(values)
    k = (len(values_sorted) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return int(values_sorted[int(k)])
    d0 = values_sorted[f] * (c - k)
    d1 = values_sorted[c] * (k - f)
    return int(d0 + d1)


def _aggregate_node_timings(rows: list[dict[str, Any]]) -> dict[str, list[int]]:
    by_node: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        timings = row.get("node_timings")
        if not isinstance(timings, dict):
            continue
        nodes = timings.get("nodes")
        if not isinstance(nodes, dict):
            continue
        for name, stats in nodes.items():
            if isinstance(stats, dict) and stats.get("total_ms") is not None:
                by_node[str(name)].append(int(stats["total_ms"]))
    return by_node


def _print_last_run_breakdown(row: dict[str, Any]) -> None:
    timings = row.get("node_timings")
    if not isinstance(timings, dict):
        return
    nodes = timings.get("nodes")
    if not isinstance(nodes, dict) or not nodes:
        return
    print("\nПоследний прогон (разбивка по узлам):")
    print(
        f"  trip_id={row.get('trip_id')} scope={row.get('rebuild_scope')} "
        f"total={row.get('duration_ms')} ms"
    )
    for name, stats in sorted(
        nodes.items(),
        key=lambda item: -(int(item[1].get("total_ms") or 0) if isinstance(item[1], dict) else 0),
    ):
        if not isinstance(stats, dict):
            continue
        print(
            f"  - {name}: {stats.get('total_ms', 0)} ms "
            f"(×{stats.get('count', 1)})"
        )
    tools = timings.get("tools")
    if isinstance(tools, dict) and tools:
        print("  tools:")
        for name, stats in sorted(
            tools.items(),
            key=lambda item: -(int(item[1].get("total_ms") or 0) if isinstance(item[1], dict) else 0),
        ):
            if not isinstance(stats, dict):
                continue
            print(
                f"    · {name}: {stats.get('total_ms', 0)} ms "
                f"(×{stats.get('count', 1)})"
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Метрики прогонов tourist-assistant")
    parser.add_argument("--limit", type=int, default=50, help="Сколько последних прогонов взять")
    parser.add_argument("--trip-id", type=int, default=None, help="Фильтр по trip_id")
    args = parser.parse_args(argv)

    init_db()
    rows: list[dict[str, Any]] = list_agent_runs(args.trip_id, limit=args.limit)
    if not rows:
        print("Нет данных в agent_runs. Запустите `python3 main.py` хотя бы один раз.")
        return 0

    durations = [int(r.get("duration_ms") or 0) for r in rows if r.get("duration_ms") is not None]
    costs = [float(r.get("total_cost_usd") or 0.0) for r in rows if r.get("total_cost_usd") is not None]
    tokens = [int(r.get("total_tokens") or 0) for r in rows if r.get("total_tokens") is not None]

    print(f"Прогонов: {len(rows)} (limit={args.limit})")
    print(f"Latency p50: {_percentile(durations, 0.50)} ms")
    print(f"Latency p95: {_percentile(durations, 0.95)} ms")
    if tokens:
        print(f"Tokens/run (median): {median(tokens):.0f}")
    if costs:
        print(f"Cost/run (median): ${median(costs):.6f}")
        print(f"Cost/run (p95):    ${sorted(costs)[max(0, int(len(costs) * 0.95) - 1)]:.6f}")
    else:
        print("Cost/run: нет данных (OpenAI callback не дал стоимость).")

    node_agg = _aggregate_node_timings(rows)
    if node_agg:
        print("\nPer-node total_ms (p50 по прогонам с метриками):")
        for name in sorted(node_agg, key=lambda n: -_percentile(node_agg[n], 0.50)):
            values = node_agg[name]
            print(f"  - {name}: p50={_percentile(values, 0.50)} ms (n={len(values)})")

    _print_last_run_breakdown(rows[0])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
