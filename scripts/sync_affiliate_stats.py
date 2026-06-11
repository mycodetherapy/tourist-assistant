"""Синхронизация affiliate-статистики Travelpayouts → SQLite."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from db.connection import init_db

_SYNC_MODULE_PATH = ROOT / "services" / "affiliate_sync.py"
_spec = importlib.util.spec_from_file_location("affiliate_sync", _SYNC_MODULE_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"Не удалось загрузить {_SYNC_MODULE_PATH}")
_affiliate_sync = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_affiliate_sync)
sync_affiliate_stats = _affiliate_sync.sync_affiliate_stats


def _affiliate_api_token() -> str:
    return os.getenv("TRAVELPAYOUTS_API_KEY", "").strip()


def main() -> None:
    if not _affiliate_api_token():
        raise SystemExit(
            "Ошибка: не задан TRAVELPAYOUTS_API_KEY (Profile → API token в Travelpayouts)."
        )
    init_db()
    days = 30
    if len(sys.argv) > 1:
        days = int(sys.argv[1])
    count = sync_affiliate_stats(days=days)
    print(f"Синхронизировано строк: {count} (за {days} дн.)")


if __name__ == "__main__":
    main()
