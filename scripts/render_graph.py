#!/usr/bin/env python3
"""Рендер PNG-схемы LangGraph из agents/graph.py (для README)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "docs" / "assets" / "graph.png"


def render(out: Path) -> None:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    from agents.graph import app

    out.parent.mkdir(parents=True, exist_ok=True)
    png = app.get_graph().draw_mermaid_png()
    out.write_bytes(png)
    print(f"Wrote {out} ({len(png)} bytes)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Сгенерировать PNG графа LangGraph для документации.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Путь к PNG (по умолчанию: {DEFAULT_OUT.relative_to(ROOT)})",
    )
    args = parser.parse_args()
    render(args.output.resolve())


if __name__ == "__main__":
    main()
