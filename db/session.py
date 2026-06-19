"""PostgreSQL engine and session (optional; SQLite remains default for API)."""

from __future__ import annotations

import os
from contextlib import contextmanager
from functools import lru_cache
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def get_database_url() -> str | None:
    """Postgres URL when set; otherwise API uses SQLite via db.connection."""
    raw = os.getenv("DATABASE_URL", "").strip()
    return raw or None


def is_postgres_enabled() -> bool:
    return get_database_url() is not None


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    url = get_database_url()
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return create_engine(url, pool_pre_ping=True)


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(
        bind=get_engine(),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


@contextmanager
def pg_session() -> Generator[Session, None, None]:
    """Transactional PostgreSQL session."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def clear_engine_cache() -> None:
    """For tests: reset cached engine after env change."""
    get_engine.cache_clear()  # type: ignore[attr-defined]
    get_session_factory.cache_clear()  # type: ignore[attr-defined]
