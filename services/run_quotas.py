"""Per-user graph run quotas (Redis sliding window)."""

from __future__ import annotations

import os
import time


class RunQuotaError(Exception):
    """Превышен лимит прогонов для пользователя."""

    def __init__(self, message: str, *, limit: int, window_sec: int = 3600) -> None:
        super().__init__(message)
        self.limit = limit
        self.window_sec = window_sec


def _full_limit() -> int:
    return int(os.getenv("RUN_QUOTA_FULL_PER_HOUR", "5"))


def _partial_limit() -> int:
    return int(os.getenv("RUN_QUOTA_PARTIAL_PER_HOUR", "10"))


def _window_sec() -> int:
    return int(os.getenv("RUN_QUOTA_WINDOW_SEC", "3600"))


def _bucket_key(user_id: int, scope: str) -> str:
    bucket = "full" if scope == "full" else "partial"
    window = _window_sec()
    slot = int(time.time()) // window
    return f"run_quota:{user_id}:{bucket}:{slot}"


def quotas_enabled() -> bool:
    from db.redis_client import is_redis_enabled

    return is_redis_enabled()


def check_and_consume_run_quota(*, user_id: int, scope: str) -> None:
    """
    Увеличивает счётчик прогонов пользователя. Бросает RunQuotaError при превышении.
    Без REDIS_URL — no-op (локальная разработка).
    """
    if not quotas_enabled():
        return

    from db.redis_client import get_redis

    limit = _full_limit() if scope == "full" else _partial_limit()
    window = _window_sec()
    key = _bucket_key(user_id, scope)
    client = get_redis()
    count = int(client.incr(key))
    if count == 1:
        client.expire(key, window)
    if count > limit:
        client.decr(key)
        label = "полных сборок" if scope == "full" else "пересборок маршрутов"
        raise RunQuotaError(
            f"Лимит {label}: {limit} в час. Попробуйте позже.",
            limit=limit,
            window_sec=window,
        )


def clear_quota_cache() -> None:
    """Сброс клиента Redis (тесты)."""
    from db.redis_client import clear_redis_cache

    clear_redis_cache()
