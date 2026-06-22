"""Инициализация PostgreSQL через Alembic."""

from __future__ import annotations


def init_db() -> None:
    """Создаёт/обновляет схему Postgres (alembic upgrade head)."""
    from db.postgres.bootstrap import init_postgres_db

    init_postgres_db()
