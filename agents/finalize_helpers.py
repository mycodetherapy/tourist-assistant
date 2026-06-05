"""Подготовка контекста для finalize: билеты из tool, без тяжёлого JSON."""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from langchain_core.messages import HumanMessage, ToolMessage

from models.schemas import ProgramDraft
from models.tickets import TicketsSearchOutput
from planning.rebuild import required_tools_for_scope, resolve_tool_name
from search.ticket_links import format_offers_summary
from search.tickets_search import run_tickets_search

_GARBAGE_TICKETS = re.compile(r"^[\s:{}\[\]]+$")
_FINALIZE_MAX_TOOL_CHARS = 12_000


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
    """Берёт готовый markdown билетов из последнего search_roundtrip_tickets."""
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
    """Источники по приоритету: tool в истории → живой run_tickets_search → base_program."""
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


def _truncate_text(text: str, limit: int) -> str:
    t = (text or "").strip()
    if len(t) <= limit:
        return t
    return t[:limit].rsplit("\n", 1)[0] + "\n…"


def slim_tool_message_for_finalize(msg: ToolMessage) -> ToolMessage:
    """Оставляет только digest/summary — без массивов search.results."""
    raw = msg.content if isinstance(msg.content, str) else str(msg.content)
    name = msg.name or ""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return ToolMessage(
            content=_truncate_text(raw, 4000),
            tool_call_id=msg.tool_call_id,
            name=name,
        )

    if not isinstance(data, dict):
        return ToolMessage(content=raw[:4000], tool_call_id=msg.tool_call_id, name=name)

    if data.get("category") == "tickets" or name == "search_roundtrip_tickets":
        slim = {
            "schema_version": data.get("schema_version"),
            "category": "tickets",
            "summary_for_llm": data.get("summary_for_llm", ""),
            "instruction": data.get("instruction", ""),
            "warning": data.get("warning"),
            "avia_api_status": data.get("avia_api_status"),
            "offers_count": data.get("offers_count"),
        }
    elif name == "search_culture_events":
        slim = {
            "category": "events",
            "digest": data.get("digest", ""),
            "walking_area": data.get("walking_area", ""),
            "results_count": data.get("results_count"),
            "instruction": _truncate_text(str(data.get("instruction", "")), 400),
            "warning": data.get("warning"),
        }
    elif name in ("search_dining", "search_dining_and_transport"):
        slim = {
            "category": "dining",
            "restaurants_digest": _truncate_text(
                str(data.get("restaurants_digest", "") or data.get("digest", "")), 3500
            ),
            "walking_area": data.get("walking_area", ""),
            "instruction": _truncate_text(str(data.get("instruction", "")), 400),
            "warning": data.get("warning"),
        }
    else:
        slim = {
            k: v
            for k, v in data.items()
            if k not in ("search", "results") and not isinstance(v, (list, dict))
        }

    content = json.dumps(slim, ensure_ascii=False, indent=2)
    if len(content) > _FINALIZE_MAX_TOOL_CHARS:
        content = content[:_FINALIZE_MAX_TOOL_CHARS] + "\n…"
    return ToolMessage(content=content, tool_call_id=msg.tool_call_id, name=name)


def _collect_latest_tool_messages(
    messages: list[Any],
    *,
    rebuild_scope: str,
) -> list[ToolMessage]:
    """Последние ToolMessage по нужным инструментам (до slim)."""
    if rebuild_scope == "lifehacks":
        return []

    needed = set(required_tools_for_scope(rebuild_scope))
    latest: dict[str, ToolMessage] = {}
    for msg in messages:
        if not isinstance(msg, ToolMessage) or not msg.name:
            continue
        canonical = resolve_tool_name(msg.name)
        if canonical in needed:
            latest[canonical] = msg

    return [
        latest[name]
        for name in (
            "search_roundtrip_tickets",
            "search_culture_events",
            "search_dining",
        )
        if name in latest
    ]


def prepare_finalize_messages(
    messages: list[Any],
    *,
    rebuild_scope: str = "full",
) -> list[HumanMessage]:
    """
    Для finalize — slim-данные инструментов в HumanMessage.
    ToolMessage без предшествующего tool_calls OpenAI API не принимает.
    """
    tool_messages = _collect_latest_tool_messages(messages, rebuild_scope=rebuild_scope)
    if not tool_messages:
        return []

    blocks: list[str] = []
    for msg in tool_messages:
        slim = slim_tool_message_for_finalize(msg)
        name = slim.name or "tool"
        blocks.append(f"### {name}\n{slim.content}")

    return [
        HumanMessage(
            content=(
                "Результаты инструментов (используй как источник фактов):\n\n"
                + "\n\n".join(blocks)
            )
        )
    ]


_DINING_TOOL_NAMES = frozenset({"search_dining", "search_dining_and_transport"})


def _tool_payload(messages: list[Any], tool_name: str) -> dict[str, Any]:
    for msg in reversed(messages):
        if not isinstance(msg, ToolMessage):
            continue
        name = msg.name or ""
        if tool_name in _DINING_TOOL_NAMES:
            if name not in _DINING_TOOL_NAMES:
                continue
        elif name != tool_name:
            continue
        raw = msg.content if isinstance(msg.content, str) else str(msg.content)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    return {}


def build_fallback_program_draft(
    messages: list[Any],
    *,
    city: str,
    walking_area: str = "",
) -> ProgramDraft:
    """Сборка черновика из digest без LLM (если ответ обрезан по length)."""
    from search.digest_format import clean_events_display, format_events_digest

    events_data = _tool_payload(messages, "search_culture_events")
    dining_data = _tool_payload(messages, "search_dining")

    events_raw = str(events_data.get("digest", "")).strip()
    if not events_raw:
        search_block = events_data.get("search")
        if isinstance(search_block, dict):
            results = search_block.get("results")
            if isinstance(results, list):
                events_raw = format_events_digest(results)
    events = clean_events_display(events_raw) if events_raw else (
        "Мероприятия: уточните на сайтах музеев города."
    )

    dining = _truncate_text(
        str(dining_data.get("restaurants_digest", "") or dining_data.get("digest", "")),
        3500,
    )
    if not dining:
        dining = "Питание: см. restaurants_digest в повторном поиске."

    area = (
        walking_area
        or str(events_data.get("walking_area", ""))
        or str(dining_data.get("walking_area", ""))
        or "центр"
    )
    from agents.lifehacks_quality import build_default_lifehacks

    lifehacks = build_default_lifehacks(
        city=city,
        walking_area=area,
        search_context=walking_area,
    )

    return ProgramDraft(
        events=events,
        dining=dining,
        lifehacks=lifehacks,
    )


def _coerce_program_draft(result: Any) -> ProgramDraft:
    """LangChain structured output может вернуть ProgramDraft или обёртку с .parsed."""
    if isinstance(result, ProgramDraft):
        return result
    parsed = getattr(result, "parsed", None)
    if isinstance(parsed, ProgramDraft):
        return parsed
    if isinstance(parsed, dict):
        return ProgramDraft(**parsed)
    if isinstance(result, dict):
        return ProgramDraft(**result)
    raise TypeError(f"Unexpected structured output type: {type(result)!r}")


def invoke_program_draft(
    llm_final: Any,
    *,
    system: Any,
    tool_messages: list[Any],
    human: HumanMessage,
    state_messages: list[Any],
    city: str,
    walking_area: str = "",
) -> ProgramDraft:
    """Вызов structured output с fallback при обрезке ответа (length)."""
    prompt = [system, *tool_messages, human]  # tool_messages — HumanMessage, не ToolMessage
    try:
        draft = _coerce_program_draft(llm_final.invoke(prompt))
        from agents.lifehacks_quality import clean_lifehacks_display

        fields = draft.model_dump()
        fields["lifehacks"] = clean_lifehacks_display(
            fields.get("lifehacks", ""),
            city=city or "город",
            walking_area=walking_area,
            search_context=walking_area,
        )
        return ProgramDraft(**fields)
    except Exception as exc:
        err_name = type(exc).__name__
        err_text = str(exc).lower()
        if "length" not in err_text and err_name not in (
            "LengthFinishReasonError",
            "OutputParserException",
        ):
            raise
        print(
            "  [writer] ответ LLM обрезан (length) — сборка из digest без повторного вызова."
        )
        return build_fallback_program_draft(
            state_messages,
            city=city or "город",
            walking_area=walking_area,
        )
