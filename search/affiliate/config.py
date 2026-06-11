"""Настройки affiliate из .env."""

from __future__ import annotations

import os


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def affiliate_enabled() -> bool:
    return _env_bool("AFFILIATE_ENABLED", default=True)


def affiliate_marker() -> str:
    return os.getenv("TRAVELPAYOUTS_MARKER", "").strip()


def affiliate_trs() -> int | None:
    raw = os.getenv("TRAVELPAYOUTS_TRS", "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def affiliate_api_token() -> str:
    return os.getenv("TRAVELPAYOUTS_API_KEY", "").strip()


def partner_links_available() -> bool:
    return bool(
        affiliate_enabled()
        and affiliate_api_token()
        and affiliate_marker()
        and affiliate_trs() is not None
    )


def affiliate_aviasales_enabled() -> bool:
    return affiliate_enabled() and _env_bool("AFFILIATE_AVIASALES", default=True)


def affiliate_tutu_bus_enabled() -> bool:
    return affiliate_enabled() and _env_bool("AFFILIATE_TUTU_BUS", default=True)


def affiliate_tutu_train_enabled() -> bool:
    return affiliate_enabled() and _env_bool("AFFILIATE_TUTU_TRAIN", default=False)


def affiliate_booking_enabled() -> bool:
    return affiliate_enabled() and _env_bool("AFFILIATE_BOOKING", default=False)
