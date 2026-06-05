"""LangFuse: LangChain callbacks для трейсов LangGraph/LLM/tools.

Интеграция через `langfuse.langchain.CallbackHandler`.
В SDK v4 клиент должен быть явно создан через `Langfuse(...)`, иначе
`get_client(public_key=...)` вернёт disabled-клиент и spans не отправятся.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

_langfuse_client: Any | None = None
_langfuse_public_key: str | None = None


def langfuse_enabled() -> bool:
    return os.getenv("LANGFUSE_ENABLED", "").strip().lower() in {"1", "true", "yes"}


def _running_in_docker() -> bool:
    return (
        os.getenv("TOURIST_ASSISTANT_IN_DOCKER", "").strip() == "1"
        or Path("/.dockerenv").exists()
    )


def resolve_langfuse_host() -> str:
    """Локальный dev: LANGFUSE_HOST; в Docker — LANGFUSE_HOST_DOCKER (или override в compose)."""
    local = (os.getenv("LANGFUSE_HOST") or os.getenv("LANGFUSE_BASE_URL") or "").strip()
    docker = os.getenv("LANGFUSE_HOST_DOCKER", "").strip()
    if _running_in_docker():
        return docker or local or "http://host.docker.internal:3000"
    return local or "http://localhost:3000"


def _langfuse_credentials() -> tuple[str, str, str] | None:
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
    secret_key = os.getenv("LANGFUSE_SECRET_KEY", "").strip()
    host = resolve_langfuse_host()
    if not public_key or not secret_key:
        return None
    return public_key, secret_key, host


def _ensure_langfuse_client() -> Any | None:
    """Создаёт и регистрирует singleton Langfuse client в SDK registry."""
    global _langfuse_client, _langfuse_public_key

    creds = _langfuse_credentials()
    if creds is None:
        return None

    public_key, secret_key, host = creds
    if _langfuse_client is not None and _langfuse_public_key == public_key:
        return _langfuse_client

    try:
        from langfuse import Langfuse  # type: ignore
    except Exception:
        return None

    # CallbackHandler читает env, но явная инициализация надёжнее.
    os.environ["LANGFUSE_PUBLIC_KEY"] = public_key
    os.environ["LANGFUSE_SECRET_KEY"] = secret_key
    if host:
        os.environ["LANGFUSE_HOST"] = host

    kwargs: dict[str, str] = {
        "public_key": public_key,
        "secret_key": secret_key,
    }
    if host:
        kwargs["host"] = host

    _langfuse_client = Langfuse(**kwargs)
    _langfuse_public_key = public_key
    return _langfuse_client


def normalize_trace_id(trace_id: str) -> str:
    """OTEL/LangFuse trace id: 32 hex-символа без дефисов."""
    return trace_id.replace("-", "")


def build_langfuse_callbacks(*, trace_id: str | None = None) -> list[Any]:
    """
    Возвращает список callback handlers для LangChain/LangGraph.

    Важно: если ключи не заданы — возвращаем пустой список (трейсинг выключен).
    """
    if not langfuse_enabled():
        return []

    creds = _langfuse_credentials()
    if creds is None:
        return []

    public_key, _, _ = creds
    client = _ensure_langfuse_client()
    if client is None:
        return []

    try:
        from langfuse.langchain import CallbackHandler  # type: ignore
    except Exception:
        return []

    trace_context = None
    if trace_id:
        trace_context = {"trace_id": normalize_trace_id(trace_id)}

    return [CallbackHandler(public_key=public_key, trace_context=trace_context)]


def flush_langfuse() -> None:
    """Сбрасывает буфер spans/generations в LangFuse (вызывать после invoke)."""
    if not langfuse_enabled():
        return

    client = _ensure_langfuse_client()
    if client is None:
        return

    try:
        if getattr(client, "_tracing_enabled", True):
            client.flush()
    except Exception:
        pass


def langfuse_metadata(
    *,
    trip_id: int | None,
    rebuild_scope: str | None,
    retry_count: int | None,
) -> dict[str, Any]:
    """
    Динамические атрибуты трейса для LangFuse (через LangChain config.metadata).

    LangFuse LangChain integration читает:
    - langfuse_user_id
    - langfuse_session_id
    - langfuse_tags
    """
    tags: list[str] = ["app:tourist-assistant"]
    if rebuild_scope:
        tags.append(f"scope:{rebuild_scope}")
    if retry_count is not None:
        tags.append(f"retry:{retry_count}")
    if trip_id is not None:
        tags.append(f"trip:{trip_id}")
    return {
        "langfuse_user_id": "local-cli",
        "langfuse_session_id": f"trip-{trip_id}" if trip_id is not None else "trip-unknown",
        "langfuse_tags": ",".join(tags),
    }
