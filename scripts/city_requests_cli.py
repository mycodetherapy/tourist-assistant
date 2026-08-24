"""CLI заявок на города: list / accept / reject / built.

  python -m scripts.city_requests_cli list
  python -m scripts.city_requests_cli list --status=new
  python -m scripts.city_requests_cli accept 12
  python -m scripts.city_requests_cli reject 12 --note="село"
  python -m scripts.city_requests_cli built 12
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from db.postgres.city_requests import (  # noqa: E402
    list_city_requests,
    set_city_request_status,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="City requests CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="Список заявок")
    p_list.add_argument("--status", default=None)

    for name in ("accept", "reject", "built"):
        p = sub.add_parser(name, help=f"Статус → {name if name != 'built' else 'built'}")
        p.add_argument("id", type=int)
        p.add_argument("--note", default=None)

    args = parser.parse_args(argv)

    if args.cmd == "list":
        rows = list_city_requests(status=args.status)
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0

    status_map = {"accept": "accepted", "reject": "rejected", "built": "built"}
    status = status_map[args.cmd]
    row = set_city_request_status(args.id, status, note=args.note)
    if row is None:
        print(f"Заявка {args.id} не найдена", file=sys.stderr)
        return 1
    print(json.dumps(row, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
