"""Подготовка контекста для finalize: билеты из tool, без тяжёлого JSON."""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from langchain_core.messages import HumanMessage, ToolMessage

from models.routes import RouteMaterials, RouteProgram
from models.schemas import ProgramDraft
from models.tickets import TicketsSearchOutput
from planning.rebuild import required_tools_for_scope, resolve_tool_name
from search.context import get_session_preferences
from search.ticket_links import format_offers_summary, normalize_tickets_markdown
from search.ticket_passengers import passengers_for_travel_party
from search.tickets_search import run_tickets_search
from search.transport_codes import ground_transport_available, required_ticket_markers

_GARBAGE_TICKETS = re.compile(r"^[\s:{}\[\]]+$")
_FINALIZE_MAX_TOOL_CHARS = 12_000


def _is_garbage_tickets(
    text: str,
    *,
    origin_city: str = "",
    destination_city: str = "",
) -> bool:
    """Отсекает обломки structured output (:{, :[], пустые блоки)."""
    t = text.strip()
    has_ground = ground_transport_available(origin_city, destination_city)
    min_len = 80 if has_ground or not (origin_city and destination_city) else 40
    if len(t) < min_len:
        return True
    if _GARBAGE_TICKETS.match(t[:20]):
        return True
    if t.startswith(":[]") or t.startswith(":{") or t.startswith("{") and "http" not in t:
        return True
    low = t.lower()
    if "http" not in low:
        return True
    if not any(label in low for label in required_ticket_markers(origin_city, destination_city)):
        return True
    return False


def extract_tickets_summary(messages: list[Any]) -> Optional[str]:
    """Билеты из последнего search_roundtrip_tickets (offers → markdown-ссылки)."""
    for msg in reversed(messages):
        if not isinstance(msg, ToolMessage) or msg.name != "search_roundtrip_tickets":
            continue
        raw = msg.content if isinstance(msg.content, str) else str(msg.content)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        try:
            output = TicketsSearchOutput.model_validate(data)
        except Exception:
            continue
        origin_city = output.params.origin_city
        destination_city = output.params.destination_city
        if output.offers:
            prefs = get_session_preferences()
            party = prefs.travel_party if prefs else "couple"
            passengers = passengers_for_travel_party(party)
            built = normalize_tickets_markdown(
                format_offers_summary(
                    origin_city,
                    destination_city,
                    output.parsed_dates,
                    output.offers,
                    passengers=passengers,
                )
            )
            if not _is_garbage_tickets(
                built,
                origin_city=origin_city,
                destination_city=destination_city,
            ):
                return built
        summary = str(data.get("summary_for_llm", "")).strip()
        if summary:
            normalized = normalize_tickets_markdown(summary)
            if not _is_garbage_tickets(
                normalized,
                origin_city=origin_city,
                destination_city=destination_city,
            ):
                return normalized
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
        prefs = get_session_preferences()
        party = prefs.travel_party if prefs else "couple"
        output = run_tickets_search(
            origin_city, destination_city, dates, travel_party=party
        )
        summary = normalize_tickets_markdown((output.summary_for_llm or "").strip())
        if summary and not _is_garbage_tickets(
            summary,
            origin_city=origin_city,
            destination_city=destination_city,
        ):
            return summary

    if base_program:
        base_t = normalize_tickets_markdown(str(base_program.get("tickets", "")).strip())
        if base_t and not _is_garbage_tickets(
            base_t,
            origin_city=origin_city,
            destination_city=destination_city,
        ):
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
    elif resolve_tool_name(name) == "search_route_materials":
        slim = {
            "category": "route_materials",
            "materials_digest": _truncate_text(
                str(data.get("materials_digest", "") or data.get("digest", "")), 6000
            ),
            "leisure_count": data.get("leisure_count"),
            "dining_count": data.get("dining_count"),
            "instruction": _truncate_text(str(data.get("instruction", "")), 500),
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
    # При routes/events/dining поиск не обязателен, но ToolMessage в истории — учитываем.
    if rebuild_scope in ("routes", "events", "dining"):
        needed.add("search_route_materials")
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
            "search_route_materials",
        )
        if name in latest
    ]


def prepare_finalize_messages(
    messages: list[Any],
    *,
    rebuild_scope: str = "full",
    trip_id: int | None = None,
) -> list[HumanMessage]:
    """
    Для finalize — slim-данные инструментов в HumanMessage.
    ToolMessage без предшествующего tool_calls OpenAI API не принимает.
    """
    tool_messages = _collect_latest_tool_messages(messages, rebuild_scope=rebuild_scope)
    if not tool_messages and rebuild_scope in ("routes", "events", "dining"):
        if trip_id is not None:
            from search.route_materials_store import cached_materials_finalize_block

            cached = cached_materials_finalize_block(int(trip_id))
            if cached:
                return [HumanMessage(content=cached)]
        return []

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


_MATERIALS_TOOL_NAMES = frozenset(
    {
        "search_route_materials",
        "search_culture_events",
        "search_dining",
        "search_dining_and_transport",
    }
)


def _tool_payload(messages: list[Any], tool_name: str) -> dict[str, Any]:
    for msg in reversed(messages):
        if not isinstance(msg, ToolMessage):
            continue
        name = msg.name or ""
        canonical = resolve_tool_name(name)
        if tool_name in _MATERIALS_TOOL_NAMES:
            if canonical != "search_route_materials":
                continue
        elif canonical != tool_name:
            continue
        raw = msg.content if isinstance(msg.content, str) else str(msg.content)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    return {}


def _normalize_city_key(city: str) -> str:
    return city.lower().replace("ё", "е").strip()


def _materials_city_ok(materials: RouteMaterials, expected_city: str | None) -> bool:
    if not expected_city:
        return True
    return _normalize_city_key(materials.city) == _normalize_city_key(expected_city)


def load_route_materials(
    messages: list[Any],
    *,
    expected_city: str | None = None,
    trip_id: int | None = None,
) -> RouteMaterials | None:
    data = _tool_payload(messages, "search_route_materials")
    raw = data.get("materials")
    if isinstance(raw, dict):
        try:
            materials = RouteMaterials.model_validate(raw)
        except Exception:
            materials = None
        else:
            if _materials_city_ok(materials, expected_city):
                return materials
    if trip_id is not None:
        from search.route_materials_store import load_route_materials_for_trip

        cached = load_route_materials_for_trip(int(trip_id))
        if cached is not None and _materials_city_ok(cached, expected_city):
            return cached
    from search.context import get_route_materials

    session_raw = get_route_materials()
    if isinstance(session_raw, dict):
        try:
            session = RouteMaterials.model_validate(session_raw)
        except Exception:
            session = None
        else:
            if _materials_city_ok(session, expected_city):
                return session
    return None


def _routes_need_maps_finalize(program: RouteProgram) -> bool:
    if not program.cases:
        return False
    return any(not str(case.maps_route_url).strip() for case in program.cases)


def resolve_routes_program(
    messages: list[Any],
    draft_routes: dict[str, Any] | None,
    *,
    base_program: Optional[dict[str, Any]],
    transport: str = "mixed",
    pace: str = "moderate",
    expected_city: str | None = None,
    trip_id: int | None = None,
    dates: str = "",
    rebuild_scope: str = "full",
    route_feedback_snapshot: dict[str, Any] | None = None,
) -> tuple[RouteProgram, str]:
    from agents.route_postprocess import (
        build_fallback_route_program,
        build_hybrid_route_program,
        build_new_routes_respecting_likes,
        enforce_route_poi_policy,
        finalize_route_program,
        format_routes_text,
    )
    from models.routes import RouteProgram, TripRouteCase
    from program.route_feedback import (
        extract_liked_routes,
        merge_preserved_with_new_routes,
        rebuild_poi_preferences,
    )

    preserved: list[Any] = []
    prefer_poi: set[str] = set()
    banned_poi: set[str] = set()
    if route_feedback_snapshot:
        prefer_poi = set(route_feedback_snapshot.get("preferred_poi_ids") or [])
        banned_poi = set(route_feedback_snapshot.get("banned_poi_ids") or [])
        if rebuild_scope == "routes":
            for raw in route_feedback_snapshot.get("liked_cases") or []:
                preserved.append(TripRouteCase.model_validate(raw))
    elif rebuild_scope == "routes" and base_program and trip_id is not None:
        preserved = extract_liked_routes(base_program, int(trip_id))

    if trip_id is not None:
        from search.route_materials_store import ensure_route_materials_for_trip

        ensure_route_materials_for_trip(
            int(trip_id),
            city=expected_city or "",
            dates=dates,
            base_program=base_program,
        )

    materials = load_route_materials(
        messages, expected_city=expected_city, trip_id=trip_id
    )
    if not route_feedback_snapshot and trip_id is not None:
        prefer_poi, banned_poi, _disliked = rebuild_poi_preferences(
            int(trip_id), materials, preserved
        )
    program: RouteProgram | None = None
    if materials:
        draft_prog: RouteProgram | None = None
        if draft_routes:
            try:
                draft_prog = RouteProgram.model_validate(draft_routes)
            except Exception:
                draft_prog = None
        if preserved:
            program = build_new_routes_respecting_likes(
                materials,
                draft_prog if draft_prog and len(draft_prog.cases) >= 3 else None,
                preserved,
                transport=transport,
                pace=pace,
                prefer_poi_ids=prefer_poi,
                banned_poi_ids=banned_poi,
            )
        elif draft_prog and len(draft_prog.cases) >= 3:
            program = build_hybrid_route_program(
                materials,
                draft_prog,
                transport=transport,
                pace=pace,
                avoid_poi_ids=banned_poi,
                prefer_poi_ids=prefer_poi,
            )
        else:
            program = build_fallback_route_program(
                materials,
                pace=pace,
                avoid_poi_ids=banned_poi,
                prefer_poi_ids=prefer_poi,
            )
    elif draft_routes:
        try:
            program = RouteProgram.model_validate(draft_routes)
        except Exception:
            program = None
    elif base_program and base_program.get("routes") and not preserved:
        try:
            program = RouteProgram.model_validate(base_program["routes"])
        except Exception:
            program = None
    if program is None:
        program = RouteProgram(cases=[])

    if _routes_need_maps_finalize(program):
        if materials is None:
            materials = load_route_materials(
                messages, expected_city=expected_city, trip_id=trip_id
            )
        if materials is None and trip_id is not None:
            from search.route_materials_store import ensure_route_materials_for_trip

            materials = ensure_route_materials_for_trip(
                int(trip_id),
                city=expected_city or "",
                dates=dates,
                base_program=base_program,
            )
        if materials:
            program = finalize_route_program(
                program,
                materials,
                transport=transport,
                pace=pace,
                banned_poi_ids=banned_poi,
                prefer_poi_ids=prefer_poi,
            )
            if banned_poi or prefer_poi:
                program = enforce_route_poi_policy(
                    program,
                    materials,
                    banned_poi_ids=banned_poi,
                    prefer_poi_ids=prefer_poi,
                    transport=transport,
                    pace=pace,
                )

    if preserved:
        program = merge_preserved_with_new_routes(preserved, program)

    return program, format_routes_text(program)


def repair_program_routes(
    program: dict[str, Any],
    *,
    messages: list[Any] | None = None,
    trip_id: int | None = None,
    city: str = "",
    dates: str = "",
    base_program: dict[str, Any] | None = None,
    transport: str = "mixed",
    pace: str = "moderate",
) -> dict[str, Any]:
    """Дополняет maps_route_url, если в сохранённой программе они пропали."""
    routes = program.get("routes")
    if not isinstance(routes, dict):
        return program
    try:
        current = RouteProgram.model_validate(routes)
    except Exception:
        return program
    if not _routes_need_maps_finalize(current):
        return program

    materials = load_route_materials(
        messages or [], expected_city=city or None, trip_id=trip_id
    )
    if materials is None and trip_id is not None:
        from search.route_materials_store import ensure_route_materials_for_trip

        materials = ensure_route_materials_for_trip(
            int(trip_id),
            city=city or "",
            dates=dates,
            base_program=base_program,
        )
    if materials is None:
        return program

    from agents.route_postprocess import backfill_route_maps_only, format_routes_text

    repaired = backfill_route_maps_only(current, materials, transport=transport)
    if _routes_need_maps_finalize(repaired):
        return program
    updated = dict(program)
    updated["routes"] = repaired.model_dump()
    if format_routes_text(repaired):
        updated["routes_text"] = format_routes_text(repaired)
    return updated


def build_fallback_program_draft(
    messages: list[Any],
    *,
    city: str,
    walking_area: str = "",
    pace: str = "moderate",
    trip_id: int | None = None,
) -> ProgramDraft:
    """Сборка черновика маршрутов без LLM (если ответ обрезан по length)."""
    from agents.route_postprocess import build_fallback_route_program
    from models.routes import RouteMaterials

    materials = load_route_materials(
        messages, expected_city=city, trip_id=trip_id
    )
    if materials is None:
        materials = RouteMaterials(city=city, dates="")
    routes = build_fallback_route_program(materials, pace=pace)
    from agents.lifehacks_quality import build_default_lifehacks

    lifehacks = build_default_lifehacks(
        city=city,
        walking_area=walking_area or "центр",
        search_context=walking_area,
    )
    return ProgramDraft(routes=routes, lifehacks=lifehacks)


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
    trip_id: int | None = None,
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
            pace=(
                get_session_preferences().pace
                if get_session_preferences() is not None
                else "moderate"
            ),
            trip_id=trip_id,
        )
