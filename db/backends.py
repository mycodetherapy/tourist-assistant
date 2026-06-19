"""Выбор SQLite или Postgres backend для repository."""

from __future__ import annotations

from types import ModuleType

from db.session import is_postgres_enabled


def get_repository_backend() -> ModuleType:
    if is_postgres_enabled():
        from db.postgres import repository as backend

        return backend
    from db.sqlite import repository as backend

    return backend
