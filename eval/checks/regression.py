"""Уровень 4: сравнение метрик с golden snapshot."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def program_metrics(program: dict[str, Any]) -> dict[str, int]:
    """Метрики для regression без сравнения полного текста."""
    routes = program.get("routes")
    route_urls = 0
    if isinstance(routes, dict):
        cases = routes.get("cases")
        if isinstance(cases, list):
            route_urls = sum(
                1
                for case in cases
                if isinstance(case, dict) and str(case.get("maps_route_url", "")).strip()
            )
    dining = str(program.get("dining", ""))
    return {
        "restaurant_links": len(
            re.findall(r"https?://", dining, flags=re.IGNORECASE)
        ),
        "route_urls": route_urls,
        "lifehacks_len": len(str(program.get("lifehacks", ""))),
    }


def load_golden(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def compare_golden(
    metrics: dict[str, int],
    golden: dict[str, Any],
    *,
    link_tolerance: int = 1,
) -> list[str]:
    issues: list[str] = []
    expected_routes = int(golden.get("route_urls", 0))
    actual_routes = metrics.get("route_urls", 0)
    if expected_routes > 0 and actual_routes < expected_routes - link_tolerance:
        issues.append(
            f"regression route_urls: {actual_routes} < {expected_routes - link_tolerance}"
        )
    expected_links = int(golden.get("restaurant_links", 0))
    actual_links = metrics["restaurant_links"]
    if expected_links > 0 and actual_links < expected_links - link_tolerance:
        issues.append(
            f"regression links: {actual_links} < {expected_links - link_tolerance}"
        )
    return issues
