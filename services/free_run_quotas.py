"""Free-tier daily run quotas (Redis)."""

from __future__ import annotations

import os
import time


class FreeRunQuotaError(Exception):
    """Превышен дневной лимит бесплатных сборок."""

    def __init__(self, message: str, *, limit: int, window_sec: int = 86400) -> None:
        super().__init__(message)
        self.limit = limit
        self.window_sec = window_sec


def _daily_limit() -> int:
    return int(os.getenv("FREE_RUN_QUOTA_PER_DAY", "30"))


def _window_sec() -> int:
    return int(os.getenv("FREE_RUN_QUOTA_WINDOW_SEC", "86400"))


def _bucket_key(user_id: int) -> str:
    window = _window_sec()
    slot = int(time.time()) // window
    return f"free_run_quota:{user_id}:{slot}"


def free_quotas_enabled() -> bool:
    from db.redis_client import is_redis_enabled

    if os.getenv("FREE_RUN_QUOTAS_ENABLED", "true").strip().lower() in (
        "0",
        "false",
        "no",
        "off",
    ):
        return False
    return is_redis_enabled()


def check_and_consume_free_run_quota(*, user_id: int) -> None:
    """
    Увеличивает счётчик бесплатных сборок пользователя за сутки.
    Без REDIS_URL — no-op (локальная разработка).
    """
    if not free_quotas_enabled():
        return

    from db.redis_client import get_redis

    limit = _daily_limit()
    window = _window_sec()
    key = _bucket_key(user_id)
    client = get_redis()
    count = int(client.incr(key))
    if count == 1:
        client.expire(key, window)
    if count > limit:
        client.decr(key)
        raise FreeRunQuotaError(
            f"Лимит бесплатных сборок: {limit} в сутки. Попробуйте завтра или включите AI в настройках.",
            limit=limit,
            window_sec=window,
        )


def clear_free_quota_cache() -> None:
    """Сброс клиента Redis (тесты)."""
    from db.redis_client import clear_redis_cache

    clear_redis_cache()
