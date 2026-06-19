"""Postgres users and BYOK settings."""

from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from db.constants import BOOTSTRAP_USER_EMAIL, BOOTSTRAP_USER_ID
from db.models.schema import User as UserRow
from db.models.schema import UserSettings
from db.postgres._helpers import iso_dt, utc_now
from db.session import pg_session
from db.users import User, UserSettingsRow


def _row_to_user(row: UserRow) -> User:
    return User(
        id=int(row.id),
        email=row.email,
        password_hash=row.password_hash,
        google_sub=row.google_sub,
        created_at=iso_dt(row.created_at),
        updated_at=iso_dt(row.updated_at),
    )


def ensure_bootstrap_user() -> None:
    with pg_session() as session:
        existing = session.get(UserRow, BOOTSTRAP_USER_ID)
        if existing is not None:
            return
        session.add(
            UserRow(
                id=BOOTSTRAP_USER_ID,
                email=BOOTSTRAP_USER_EMAIL,
                password_hash=None,
                google_sub=None,
                created_at=utc_now(),
                updated_at=utc_now(),
            )
        )
        session.flush()


def ensure_cli_bootstrap_user() -> None:
    ensure_bootstrap_user()


def create_user(
    *,
    email: str,
    password_hash: str | None = None,
    google_sub: str | None = None,
) -> User:
    normalized = email.strip().lower()
    now = utc_now()
    with pg_session() as session:
        row = UserRow(
            email=normalized,
            password_hash=password_hash,
            google_sub=google_sub,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        session.flush()
        session.refresh(row)
        return _row_to_user(row)


def get_user_by_id(user_id: int) -> User | None:
    with pg_session() as session:
        row = session.get(UserRow, user_id)
        return _row_to_user(row) if row else None


def get_user_by_email(email: str) -> User | None:
    normalized = email.strip().lower()
    with pg_session() as session:
        row = session.execute(
            select(UserRow).where(func.lower(UserRow.email) == normalized)
        ).scalar_one_or_none()
        return _row_to_user(row) if row else None


def get_user_by_google_sub(google_sub: str) -> User | None:
    with pg_session() as session:
        row = session.execute(
            select(UserRow).where(UserRow.google_sub == google_sub)
        ).scalar_one_or_none()
        return _row_to_user(row) if row else None


def link_google_sub(user_id: int, google_sub: str) -> None:
    with pg_session() as session:
        session.execute(
            update(UserRow)
            .where(UserRow.id == user_id)
            .values(google_sub=google_sub, updated_at=utc_now())
        )


def get_user_settings(user_id: int) -> UserSettingsRow | None:
    with pg_session() as session:
        row = session.get(UserSettings, user_id)
        if row is None:
            return None
        return UserSettingsRow(
            user_id=int(row.user_id),
            llm_api_key_enc=row.llm_api_key_enc,
            llm_base_url=row.llm_base_url,
            llm_model=row.llm_model,
            updated_at=iso_dt(row.updated_at),
        )


def upsert_user_settings(
    user_id: int,
    *,
    llm_api_key_enc: str | None = None,
    llm_base_url: str | None = None,
    llm_model: str | None = None,
    clear_llm_key: bool = False,
) -> UserSettingsRow:
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
    now = utc_now()
    with pg_session() as session:
        stmt = pg_insert(UserSettings).values(
            user_id=user_id,
            llm_api_key_enc=enc,
            llm_base_url=base_url,
            llm_model=model,
            updated_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id"],
            set_={
                "llm_api_key_enc": enc,
                "llm_base_url": base_url,
                "llm_model": model,
                "updated_at": now,
            },
        )
        session.execute(stmt)
    row = get_user_settings(user_id)
    assert row is not None
    return row


def clear_user_llm_key(user_id: int) -> None:
    upsert_user_settings(user_id, clear_llm_key=True)
