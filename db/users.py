"""Пользователи SaaS и зашифрованные настройки BYOK (facade)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

__all__ = [
    "User",
    "UserSettingsRow",
    "ensure_bootstrap_user",
    "ensure_cli_bootstrap_user",
    "create_user",
    "get_user_by_id",
    "get_user_by_email",
    "get_user_by_google_sub",
    "link_google_sub",
    "get_user_settings",
    "upsert_user_settings",
    "clear_user_llm_key",
]


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
    llm_mode: str
    updated_at: str


def __getattr__(name: str):
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from db.backends import get_users_backend

    return getattr(get_users_backend(), name)
