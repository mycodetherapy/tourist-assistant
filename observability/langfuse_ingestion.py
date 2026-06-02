"""LangFuse: надёжная отправка трейсов через Public Ingestion API.

CallbackHandler в langfuse/langchain зависит от версии SDK и может молча отключаться.
Для диплома важнее иметь реальные трейсы запусков: этот модуль отправляет минимум
`trace-create` на каждый прогон графа.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import uuid
from typing import Any

import requests


def _utc_ts() -> str:
    return _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def langfuse_ingestion_enabled() -> bool:
    return os.getenv("LANGFUSE_ENABLED", "").strip().lower() in {"1", "true", "yes"}


def _host() -> str:
    raw = os.getenv("LANGFUSE_HOST") or os.getenv("LANGFUSE_BASE_URL") or "http://localhost:3000"
    return raw.rstrip("/")


def send_trace_create(
    *,
    trace_id: str | None = None,
    name: str,
    input_data: dict[str, Any] | None = None,
    output_data: dict[str, Any] | None = None,
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> str | None:
    """Создаёт trace в LangFuse. Возвращает trace_id или None при ошибке."""
    if not langfuse_ingestion_enabled():
        return None

    public_key = (os.getenv("LANGFUSE_PUBLIC_KEY") or "").strip()
    secret_key = (os.getenv("LANGFUSE_SECRET_KEY") or "").strip()
    if not public_key or not secret_key:
        return None

    tid = trace_id or str(uuid.uuid4())
    ts = _utc_ts()
    body: dict[str, Any] = {
        "id": tid,
        "timestamp": ts,
        "name": name,
        "public": False,
    }
    if input_data is not None:
        body["input"] = input_data
    if output_data is not None:
        body["output"] = output_data
    if tags:
        body["tags"] = tags
    if metadata:
        body["metadata"] = metadata

    payload = {"batch": [{"id": tid, "timestamp": ts, "type": "trace-create", "body": body}]}

    try:
        r = requests.post(
            f"{_host()}/api/public/ingestion",
            auth=(public_key, secret_key),
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload, ensure_ascii=False),
            timeout=10,
        )
        # 207 with per-event statuses
        if r.status_code not in (200, 201, 207):
            return None
        return tid
    except Exception:
        return None

