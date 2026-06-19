"""Postgres startup: Alembic migrations + bootstrap user."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config


def init_postgres_db() -> None:
    """Применяет миграции и гарантирует bootstrap user."""
    root = Path(__file__).resolve().parents[2]
    cfg = Config(str(root / "alembic.ini"))
    command.upgrade(cfg, "head")
    from db.postgres import users as pg_users

    pg_users.ensure_bootstrap_user()
