#!/usr/bin/env python3
"""Create TEST_DATABASE_URL database if missing and apply Alembic migrations."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]


def _database_name(url: str) -> str:
    parsed = urlparse(url.replace("+psycopg", ""))
    name = (parsed.path or "").lstrip("/").split("?")[0].strip()
    if not name:
        raise ValueError(f"Cannot parse database name from URL: {url!r}")
    return name


def _admin_url(url: str) -> str:
    base, _, _query = url.partition("?")
    head, _, _ = base.rpartition("/")
    return f"{head}/postgres"


def main() -> int:
    load_dotenv(ROOT / ".env")
    test_url = os.getenv("TEST_DATABASE_URL", "").strip()
    if not test_url:
        return 0

    db_name = _database_name(test_url)
    if not db_name.endswith("_test"):
        print(
            f"TEST_DATABASE_URL must point to a database ending with '_test', got {db_name!r}",
            file=sys.stderr,
        )
        return 1

    admin = create_engine(_admin_url(test_url), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": db_name},
        ).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{db_name}"'))
            print(f"Created database {db_name!r}")

    env = {**os.environ, "DATABASE_URL": test_url}
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
        env=env,
        check=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
