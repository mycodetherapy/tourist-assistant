"""Стабильный ключ пункта подборки для хранения оценок."""

from __future__ import annotations

import hashlib
import re

_MAX_TEXT = 500


def normalize_item_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def make_item_key(section: str, text: str) -> str:
    """Хеш содержимого пункта — не зависит от индекса и версии программы."""
    payload = f"{section}:{normalize_item_text(text)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def make_route_stop_key(poi_id: str) -> str:
    """Стабильный ключ оценки POI-остановки (обратимый, не хеш)."""
    pid = (poi_id or "").strip()
    if not pid:
        raise ValueError("poi_id обязателен")
    return f"poi:{pid}"


def parse_route_stop_key(item_key: str) -> str | None:
    key = (item_key or "").strip()
    if key.startswith("poi:") and len(key) > 4:
        return key[4:]
    return None
