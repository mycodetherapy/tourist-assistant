"""Уровень 4: сравнение метрик с golden snapshot."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def program_metrics(program: dict[str, Any]) -> dict[str, int]:
    """Метрики для regression без сравнения полного текста."""
    dining = str(program.get("dining", ""))
    return {
        "restaurant_links": len(
            re.findall(r"https?://", dining, flags=re.IGNORECASE)
        ),
        "tickets_len": len(str(program.get("tickets", ""))),
        "events_len": len(str(program.get("events", ""))),
    }


def load_golden(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def compare_golden(
    metrics: dict[str, int],
    golden: dict[str, Any],
    *,
    link_tolerance: int = 3,
) -> list[str]:
    issues: list[str] = []
    expected_links = int(golden.get("restaurant_links", 0))
    actual = metrics["restaurant_links"]
    if expected_links > 0 and actual < expected_links - link_tolerance:
        issues.append(
            f"regression links: {actual} < {expected_links - link_tolerance}"
        )
    return issues
