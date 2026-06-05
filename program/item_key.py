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
