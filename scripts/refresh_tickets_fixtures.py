#!/usr/bin/env python3
"""
Обновляет tickets в eval/fixtures по живому search_roundtrip_tickets.

Использует .env (TRAVELPAYOUTS_API_KEY для API авиа).
Запуск: python3 scripts/refresh_tickets_fixtures.py [--suite smoke]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

load_dotenv(_ROOT / ".env")

from eval.checks.regression import program_metrics  # noqa: E402
from search.tickets_search import run_tickets_search  # noqa: E402
from search.tool_logging import parse_tool_result  # noqa: E402

_FIXTURES = _ROOT / "eval" / "fixtures"
_GOLDEN = _ROOT / "eval" / "golden"
_DATASET = _ROOT / "eval" / "dataset"


def _load_cases(suite: str) -> list[dict]:
    path = _DATASET / f"{suite}.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return list(data.get("cases", []))


def _program_tickets_from_output(payload: dict) -> str:
    summary = str(payload.get("summary_for_llm", "")).strip()
    if summary:
        return summary
    lines = ["Билеты (из offers tool):"]
    for offer in payload.get("offers", []):
        lines.append(f"- {offer.get('label')}: {offer.get('booking_url')}")
    return "\n".join(lines)


def _refresh_case(case: dict) -> None:
    case_id = case["id"]
    origin = case["origin_city"]
    dest = case["city"]
    dates = case["dates"]

    output = run_tickets_search(origin, dest, dates)
    payload = json.loads(output.model_dump_json())
    metrics = parse_tool_result(output.model_dump_json())

    program_path = _FIXTURES / f"{case_id}_program.json"
    runs_path = _FIXTURES / f"{case_id}_tool_runs.json"
    golden_path = _GOLDEN / f"{case_id}.json"

    if not program_path.is_file():
        print(f"  SKIP {case_id}: нет {program_path.name}")
        return

    program = json.loads(program_path.read_text(encoding="utf-8"))
    program["tickets"] = _program_tickets_from_output(payload)
    program_path.write_text(
        json.dumps(program, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    runs: list[dict] = []
    if runs_path.is_file():
        runs = json.loads(runs_path.read_text(encoding="utf-8"))

    ticket_row = {
        "tool_name": "search_roundtrip_tickets",
        "live_data": metrics["live_data"],
        "results_count": metrics["results_count"],
        "raw_results_count": metrics["raw_results_count"],
        "provider": metrics.get("provider"),
        "avia_api_status": payload.get("avia_api_status"),
    }
    replaced = False
    for i, row in enumerate(runs):
        if row.get("tool_name") == "search_roundtrip_tickets":
            runs[i] = ticket_row
            replaced = True
            break
    if not replaced:
        runs.insert(0, ticket_row)
    runs_path.write_text(
        json.dumps(runs, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    if golden_path.is_file():
        golden = json.loads(golden_path.read_text(encoding="utf-8"))
        m = program_metrics(program)
        golden["tickets_len"] = m["tickets_len"]
        golden_path.write_text(
            json.dumps(golden, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    api = payload.get("avia_api_status")
    print(
        f"  {case_id}: offers={metrics['results_count']} "
        f"avia_api={api} tickets_len={len(program['tickets'])}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", default="smoke")
    parser.add_argument("--case", default=None)
    args = parser.parse_args()

    cases = _load_cases(args.suite)
    if args.case:
        cases = [c for c in cases if c["id"] == args.case]

    print(f"Обновление tickets fixtures, suite={args.suite}, cases={len(cases)}")
    for case in cases:
        _refresh_case(case)
    print("Готово.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
