"""LangFuse: LangChain callbacks для трейсов LangGraph/LLM/tools.

Интеграция сделана через `langfuse.langchain.CallbackHandler`, чтобы:
- автоматически видеть вызовы LLM и tools внутри LangGraph,
- не ломать существующий опциональный LangSmith-трейсинг,
- включать/выключать через env без изменений кода.
"""

from __future__ import annotations

import os
from typing import Any


def langfuse_enabled() -> bool:
    return os.getenv("LANGFUSE_ENABLED", "").strip().lower() in {"1", "true", "yes"}


def build_langfuse_callbacks() -> list[Any]:
    """
    Возвращает список callback handlers для LangChain/LangGraph.

    Важно: если ключи не заданы — возвращаем пустой список (трейсинг выключен).
    """
    if not langfuse_enabled():
        return []

    public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
    secret_key = os.getenv("LANGFUSE_SECRET_KEY", "").strip()
    # Langfuse SDK historically used LANGFUSE_HOST; some setups use LANGFUSE_BASE_URL.
    host = (os.getenv("LANGFUSE_HOST") or os.getenv("LANGFUSE_BASE_URL") or "").strip()
    if not public_key or not secret_key:
        return []

    # Lazy import: зависимость опциональная для пользователей без LangFuse.
    try:
        from langfuse import get_client  # type: ignore
        from langfuse.langchain import CallbackHandler  # type: ignore
    except Exception:
        # Если пакет не установлен, не падаем — просто отключаем LangFuse.
        return []

    # В нашей версии `langfuse.langchain.CallbackHandler` не принимает secret_key/host аргументы
    # (он читает их из env: LANGFUSE_PUBLIC_KEY/LANGFUSE_SECRET_KEY/LANGFUSE_HOST).
    if host:
        os.environ["LANGFUSE_HOST"] = host
    os.environ["LANGFUSE_PUBLIC_KEY"] = public_key
    os.environ["LANGFUSE_SECRET_KEY"] = secret_key

    # В v4, чтобы callbacks реально отправляли события, нужно инициализировать singleton client.
    # Иначе SDK отключает трейсинг и пишет warning "client initialized without public_key".
    _ = get_client(public_key=public_key)

    return [CallbackHandler(public_key=public_key)]


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
    # LangFuse integration ожидает строки (а не list) в metadata.
    return {
        "langfuse_user_id": "local-cli",
        "langfuse_session_id": f"trip-{trip_id}" if trip_id is not None else "trip-unknown",
        "langfuse_tags": ",".join(tags),
    }

