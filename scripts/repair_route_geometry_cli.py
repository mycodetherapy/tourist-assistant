#!/usr/bin/env python3
"""CLI: repair_program_routes с backfill route_geometry (stdin JSON → stdout JSON)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv

load_dotenv(_ROOT / ".env")

from agents.finalize_helpers import repair_program_routes  # noqa: E402


def main() -> int:
    payload = json.load(sys.stdin)
    program = payload.get("program")
    if not isinstance(program, dict):
        print("program must be an object", file=sys.stderr)
        return 1
    trip_id = payload.get("trip_id")
    result = repair_program_routes(
        program,
        trip_id=int(trip_id) if trip_id is not None else None,
        city=str(payload.get("city") or ""),
        dates=str(payload.get("dates") or ""),
        transport=str(payload.get("transport") or "mixed"),
        pace=str(payload.get("pace") or "moderate"),
    )
    json.dump(result, sys.stdout, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
