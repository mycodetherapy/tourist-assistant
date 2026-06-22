"""JWT access tokens."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import jwt

_ALGORITHM = "HS256"


def _secret() -> str:
    secret = os.getenv("JWT_SECRET", "").strip()
    if not secret:
        raise RuntimeError("JWT_SECRET не задан")
    return secret


def _ttl_minutes() -> int:
    raw = os.getenv("JWT_ACCESS_TTL_MINUTES", "60").strip()
    try:
        return max(5, int(raw))
    except ValueError:
        return 60


def create_access_token(*, user_id: int, email: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "email": email,
        "iat": now,
        "exp": now + timedelta(minutes=_ttl_minutes()),
    }
    return jwt.encode(payload, _secret(), algorithm=_ALGORITHM)


def decode_access_token(token: str) -> dict[str, object]:
    return jwt.decode(token, _secret(), algorithms=[_ALGORITHM])
