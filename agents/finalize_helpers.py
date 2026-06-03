"""Подготовка контекста для finalize: билеты из tool, без тяжёлого JSON."""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from langchain_core.messages import ToolMessage

from models.tickets import TicketsSearchOutput
from search.ticket_links import format_offers_summary
from search.tickets_search import run_tickets_search

_GARBAGE_TICKETS = re.compile(r"^[\s:{}\[\]]+$")


def _is_garbage_tickets(text: str) -> bool:
    """Отсекает обломки structured output (:{, :[], пустые блоки)."""
    t = text.strip()
    if len(t) < 80:
        return True
    if _GARBAGE_TICKETS.match(t[:20]):
        return True
    if t.startswith(":[]") or t.startswith(":{") or t.startswith("{") and "http" not in t:
        return True
    low = t.lower()
    if "http" not in low:
        return True
    if "самол" not in low and "поезд" not in low and "автобус" not in low:
        return True
    return False


def extract_tickets_summary(messages: list[Any]) -> Optional[str]:
    """
    Берёт готовый markdown билетов из последнего search_roundtrip_tickets.
    """
    for msg in reversed(messages):
        if not isinstance(msg, ToolMessage) or msg.name != "search_roundtrip_tickets":
            continue
        raw = msg.content if isinstance(msg.content, str) else str(msg.content)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        summary = str(data.get("summary_for_llm", "")).strip()
        if summary and not _is_garbage_tickets(summary):
            return summary
        try:
            output = TicketsSearchOutput.model_validate(data)
        except Exception:
            continue
        if output.offers:
            built = format_offers_summary(
                output.params.origin_city,
                output.params.destination_city,
                output.parsed_dates,
                output.offers,
            )
            if not _is_garbage_tickets(built):
                return built
    return None


def resolve_tickets_section(
    *,
    messages: list[Any],
    base_program: Optional[dict[str, Any]],
    origin_city: str,
    destination_city: str,
    dates: str,
    rebuild_scope: str,
) -> str:
    """
    Источники по приоритету: tool в истории → живой run_tickets_search → base_program.
    """
    from_tool = extract_tickets_summary(messages)
    if from_tool:
        return from_tool

    if rebuild_scope in ("full", "tickets"):
        output = run_tickets_search(origin_city, destination_city, dates)
        summary = (output.summary_for_llm or "").strip()
        if summary and not _is_garbage_tickets(summary):
            return summary

    if base_program:
        base_t = str(base_program.get("tickets", "")).strip()
        if base_t and not _is_garbage_tickets(base_t):
            return base_t

    return (
        "Билеты: не удалось собрать раздел. "
        "Повторите поиск (search_roundtrip_tickets) или проверьте даты и TRAVELPAYOUTS_API_KEY."
    )


def slim_tool_message_for_finalize(msg: ToolMessage) -> ToolMessage:
    """Убирает тяжёлый offers[] — LLM видит только summary."""
    raw = msg.content if isinstance(msg.content, str) else str(msg.content)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return ToolMessage(
            content=raw[:4000],
            tool_call_id=msg.tool_call_id,
            name=msg.name,
        )
    if data.get("category") != "tickets":
        return msg
    slim = {
        "schema_version": data.get("schema_version"),
        "category": "tickets",
        "summary_for_llm": data.get("summary_for_llm", ""),
        "instruction": data.get("instruction", ""),
        "warning": data.get("warning"),
        "avia_api_status": data.get("avia_api_status"),
        "offers_count": data.get("offers_count"),
    }
    return ToolMessage(
        content=json.dumps(slim, ensure_ascii=False, indent=2),
        tool_call_id=msg.tool_call_id,
        name=msg.name,
    )


def prepare_finalize_messages(messages: list[Any]) -> list[Any]:
    """Сжимает tool payload билетов перед вызовом llm_final."""
    return [
        slim_tool_message_for_finalize(m)
        if isinstance(m, ToolMessage) and m.name == "search_roundtrip_tickets"
        else m
        for m in messages
    ]
