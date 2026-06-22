"""PostgreSQL repository backend."""

from __future__ import annotations

from types import ModuleType


def get_repository_backend() -> ModuleType:
    from db.postgres import repository as backend

    return backend


def get_users_backend() -> ModuleType:
    from db.postgres import users as backend

    return backend
