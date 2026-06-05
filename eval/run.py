"""
Запуск eval: python -m eval.run --suite smoke [--with-llm] [--case ID]

Уровни 1–2 работают на fixture JSON; --live (будущее) — живой граф.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from eval.checks.deterministic import run_deterministic_checks
from eval.checks.llm_judge import run_llm_judge
from eval.checks.regression import compare_golden, load_golden, program_metrics
from eval.checks.tools import run_tool_checks

_ROOT = Path(__file__).resolve().parent.parent
_FIXTURES = Path(__file__).resolve().parent / "fixtures"
_GOLDEN = Path(__file__).resolve().parent / "golden"
_DATASET = Path(__file__).resolve().parent / "dataset"


def _load_cases(suite: str) -> list[dict]:
    path = _DATASET / f"{suite}.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"Нет датасета: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return list(data.get("cases", []))


def _load_fixture(case_id: str) -> tuple[dict, list[dict]] | None:
    program_path = _FIXTURES / f"{case_id}_program.json"
    runs_path = _FIXTURES / f"{case_id}_tool_runs.json"
    if not program_path.is_file():
        return None
    program = json.loads(program_path.read_text(encoding="utf-8"))
    runs: list[dict] = []
    if runs_path.is_file():
        runs = json.loads(runs_path.read_text(encoding="utf-8"))
    return program, runs


def _run_case(case: dict, *, with_llm: bool) -> bool:
    case_id = case["id"]
    print(f"\n=== {case_id} ===")
    loaded = _load_fixture(case_id)
    if loaded is None:
        print(f"  SKIP: нет fixture eval/fixtures/{case_id}_program.json")
        return True

    program, runs = loaded
    expect = case.get("expect", {})
    all_issues: list[str] = []

    all_issues.extend(run_deterministic_checks(program, expect))
    all_issues.extend(run_tool_checks(runs, expect))

    golden = load_golden(_GOLDEN / f"{case_id}.json")
    if golden:
        all_issues.extend(compare_golden(program_metrics(program), golden))

    if with_llm:
        verdict, err = run_llm_judge(
            program,
            city=case.get("city", ""),
            origin_city=case.get("origin_city", ""),
        )
        if err:
            all_issues.append(f"llm_judge: {err}")
        elif verdict:
            print(
                f"  LLM judge: score={verdict.score} "
                f"prices_ok={verdict.prices_ok} city_ok={verdict.city_ok}"
            )
            if verdict.score < 3:
                all_issues.append(f"llm_judge: низкий score {verdict.score}")
            if not verdict.prices_ok:
                all_issues.append("llm_judge: prices_ok=false")
            if not verdict.city_ok:
                all_issues.append("llm_judge: city_ok=false")

    if all_issues:
        for issue in all_issues:
            print(f"  FAIL: {issue}")
        return False

    print("  PASS")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Eval tourist-assistant")
    parser.add_argument("--suite", default="smoke", help="Имя YAML в eval/dataset/")
    parser.add_argument("--case", default=None, help="Только один case id")
    parser.add_argument(
        "--with-llm",
        action="store_true",
        help="Включить LLM-as-judge (нужен LLM_API_KEY)",
    )
    args = parser.parse_args(argv)

    cases = _load_cases(args.suite)
    if args.case:
        cases = [c for c in cases if c["id"] == args.case]
        if not cases:
            print(f"Кейс {args.case!r} не найден в suite {args.suite}")
            return 1

    print(f"Eval suite={args.suite}, cases={len(cases)}")
    passed = sum(1 for c in cases if _run_case(c, with_llm=args.with_llm))
    print(f"\nИтого: {passed}/{len(cases)} passed")
    return 0 if passed == len(cases) else 1


if __name__ == "__main__":
    sys.exit(main())
