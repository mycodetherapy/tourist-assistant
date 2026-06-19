"""Пользователи SaaS и зашифрованные настройки BYOK."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from db.connection import connect
from db.constants import BOOTSTRAP_USER_EMAIL, BOOTSTRAP_USER_ID


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class User:
    id: int
    email: str
    password_hash: str | None
    google_sub: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class UserSettingsRow:
    user_id: int
    llm_api_key_enc: str | None
    llm_base_url: str | None
    llm_model: str | None
    updated_at: str


def _row_to_user(row: Any) -> User:
    return User(
        id=int(row["id"]),
        email=row["email"],
        password_hash=row["password_hash"],
        google_sub=row["google_sub"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def ensure_bootstrap_user() -> None:
    """Системный пользователь id=1 для миграции legacy-данных."""
    now = _utc_now()
    with connect() as conn:
        row = conn.execute("SELECT id FROM users WHERE id = ?", (BOOTSTRAP_USER_ID,)).fetchone()
        if row is not None:
            return
        conn.execute(
            """
            INSERT INTO users (id, email, password_hash, google_sub, created_at, updated_at)
            VALUES (?, ?, NULL, NULL, ?, ?)
            """,
            (BOOTSTRAP_USER_ID, BOOTSTRAP_USER_EMAIL, now, now),
        )
        conn.commit()


def ensure_cli_bootstrap_user() -> None:
    """Устаревшее имя — делегирует ensure_bootstrap_user."""
    ensure_bootstrap_user()


def create_user(
    *,
    email: str,
    password_hash: str | None = None,
    google_sub: str | None = None,
) -> User:
    normalized = email.strip().lower()
    now = _utc_now()
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO users (email, password_hash, google_sub, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (normalized, password_hash, google_sub, now, now),
        )
        conn.commit()
        user_id = int(cursor.lastrowid)
    user = get_user_by_id(user_id)
    assert user is not None
    return user


def get_user_by_id(user_id: int) -> User | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _row_to_user(row) if row else None


def get_user_by_email(email: str) -> User | None:
    normalized = email.strip().lower()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ? COLLATE NOCASE",
            (normalized,),
        ).fetchone()
    return _row_to_user(row) if row else None


def get_user_by_google_sub(google_sub: str) -> User | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE google_sub = ?", (google_sub,)).fetchone()
    return _row_to_user(row) if row else None


def link_google_sub(user_id: int, google_sub: str) -> None:
    now = _utc_now()
    with connect() as conn:
        conn.execute(
            "UPDATE users SET google_sub = ?, updated_at = ? WHERE id = ?",
            (google_sub, now, user_id),
        )
        conn.commit()


def get_user_settings(user_id: int) -> UserSettingsRow | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM user_settings WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    if row is None:
        return None
    return UserSettingsRow(
        user_id=int(row["user_id"]),
        llm_api_key_enc=row["llm_api_key_enc"],
        llm_base_url=row["llm_base_url"],
        llm_model=row["llm_model"],
        updated_at=row["updated_at"],
    )


def upsert_user_settings(
    user_id: int,
    *,
    llm_api_key_enc: str | None = None,
    llm_base_url: str | None = None,
    llm_model: str | None = None,
    clear_llm_key: bool = False,
) -> UserSettingsRow:
    now = _utc_now()
    existing = get_user_settings(user_id)
    enc = None if clear_llm_key else llm_api_key_enc
    if enc is None and not clear_llm_key and existing is not None:
        enc = existing.llm_api_key_enc
    base_url = llm_base_url if llm_base_url is not None else (
        existing.llm_base_url if existing else None
    )
    model = llm_model if llm_model is not None else (
        existing.llm_model if existing else None
    )
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO user_settings (user_id, llm_api_key_enc, llm_base_url, llm_model, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                llm_api_key_enc = excluded.llm_api_key_enc,
                llm_base_url = excluded.llm_base_url,
                llm_model = excluded.llm_model,
                updated_at = excluded.updated_at
            """,
            (user_id, enc, base_url, model, now),
        )
        conn.commit()
    row = get_user_settings(user_id)
    assert row is not None
    return row


def clear_user_llm_key(user_id: int) -> None:
    upsert_user_settings(user_id, clear_llm_key=True)
