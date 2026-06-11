"""Узлы LangGraph: researcher → executor|writer, critic, human_review."""

from __future__ import annotations

from time import perf_counter

from typing import Any, Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from agents.critic import run_critic
from agents.finalize_helpers import (
    invoke_program_draft,
    load_route_materials,
    prepare_finalize_messages,
    repair_program_routes,
    resolve_routes_program,
    resolve_tickets_section,
)
from agents.human_review import prompt_approve_program, prompt_reject_action
from agents.llm import get_llm_final, get_llm_with_tools
from agents.print_program import print_final_program
from db import log_tool_run, update_trip_status
from models.schemas import (
    ExecutorNodeOutput,
    FinalProgram,
    PlannerContext,
    PlannerNodeOutput,
    ProgramDraft,
    normalize_stored_program,
)
from models.state import AgentState
from planning import (
    finalize_extra_prompt,
    human_message_for_scope,
    merge_program,
    planner_tools_hint,
)
from planning.rebuild import resolve_tool_name
from search.context import clear_route_materials
from search.tool_logging import parse_tool_result
from search.tools import TOOL_MAP
from services.graph_metrics import record_tool_timing


def _normalize_city_key(city: str) -> str:
    return city.lower().replace("ё", "е").strip()


def resolve_tool_args(
    state: AgentState,
    tool_name: str,
    args: dict[str, Any] | None,
) -> dict[str, Any]:
    """Подставляет city/dates из state — LLM иногда путает город поездки."""
    merged = dict(args or {})
    resolved = resolve_tool_name(tool_name)
    if resolved == "search_route_materials":
        merged["city"] = state["city"]
        merged["dates"] = state["dates"]
    elif resolved == "search_roundtrip_tickets":
        merged["origin_city"] = state["origin_city"]
        merged["destination_city"] = state["city"]
        merged["dates"] = state["dates"]
    return merged

__all__ = [
    "critic_node",
    "executor_node",
    "finalize_node",
    "human_review_node",
    "planner_node",
    "route_after_critic",
    "route_after_human",
    "route_after_researcher",
    "route_entry",
]


def _build_planner_system_prompt(ctx: PlannerContext, rebuild_scope: str) -> str:
    """Формирует системный промпт для узла planner."""
    prefs_block = ""
    if ctx.search_context:
        prefs_block = f"\nПредпочтения пользователя (опросник): {ctx.search_context}\n"
    tools_hint = planner_tools_hint(rebuild_scope)
    return (
        "Ты — туристический ассистент. Составляешь культурную программу поездки.\n"
        f"Город поездки: {ctx.city}. Даты: {ctx.dates}. Город вылета: {ctx.origin_city}."
        f"{prefs_block}\n"
        "Инструменты: tickets=билеты; route_materials=единый пул мест досуга и ресторанов "
        "(Яндекс.Карты, poi_id + координаты). Цены — только из tool JSON.\n\n"
        "Обязанности:\n"
        "1. Билеты: search_roundtrip_tickets, не выдумывай ссылки.\n"
        "2. Маршруты: search_route_materials — пул POI на всю поездку.\n\n"
        f"{tools_hint}\n"
        f"Билеты: origin={ctx.origin_city}, destination={ctx.city}, dates={ctx.dates}. "
        f"Материалы маршрута: city={ctx.city}, dates={ctx.dates}."
    )


def planner_node(state: AgentState) -> dict[str, list[Any]]:
    """
    Узел планировщика: LLM анализирует запрос и формирует tool_calls
    для сбора данных или финальный ответ без инструментов.
    """
    rebuild_scope = state.get("rebuild_scope", "full")
    ctx = PlannerContext(
        city=state["city"],
        dates=state["dates"],
        origin_city=state["origin_city"],
        search_context=state.get("search_context", ""),
    )
    system = SystemMessage(content=_build_planner_system_prompt(ctx, rebuild_scope))
    llm_with_tools = get_llm_with_tools()
    response: AIMessage = llm_with_tools.invoke([system, *state["messages"]])

    PlannerNodeOutput(message=response)

    return {"messages": [response]}


def executor_node(state: AgentState) -> dict[str, list[ToolMessage]]:
    """
    Узел исполнителя: tool_calls → ToolMessage.
    Ошибка инструмента → текст в ToolMessage, граф продолжается (planner видит сбой).
    """
    last = state["messages"][-1]
    if not isinstance(last, AIMessage) or not last.tool_calls:
        return {"messages": []}

    tool_messages: list[ToolMessage] = []

    for call in last.tool_calls:
        name = call["name"]
        args = resolve_tool_args(state, name, call.get("args") or {})
        tool_call_id = call["id"]

        trip_id = state.get("trip_id")
        resolved = resolve_tool_name(name)
        try:
            if resolved not in TOOL_MAP:
                raise KeyError(f"Неизвестный инструмент: {name}")
            if resolved == "search_route_materials":
                clear_route_materials()
            tool_started = perf_counter()
            try:
                result = TOOL_MAP[resolved].invoke(args)
            finally:
                record_tool_timing(resolved, perf_counter() - tool_started)
            content = result if isinstance(result, str) else str(result)
        except Exception as exc:
            content = f"Ошибка выполнения инструмента {name}: {exc}"

        if trip_id is not None:
            metrics = parse_tool_result(content)
            log_tool_run(
                int(trip_id),
                name,
                args=args,
                provider=metrics.get("provider"),
                live_data=bool(metrics.get("live_data")),
                results_count=int(metrics.get("results_count", 0)),
                raw_results_count=int(metrics.get("raw_results_count", 0)),
                error=metrics.get("error"),
            )

        tool_messages.append(
            ToolMessage(content=content, tool_call_id=tool_call_id, name=name)
        )
        if (
            trip_id is not None
            and resolved == "search_route_materials"
            and not str(content).startswith("Ошибка")
        ):
            from search.route_materials_store import persist_route_materials_from_tool

            persist_route_materials_from_tool(int(trip_id), content)

    ExecutorNodeOutput(tool_messages=tool_messages)
    return {"messages": tool_messages}


def finalize_node(state: AgentState) -> dict[str, Any]:
    """
    Финальный узел: формирует структурированную программу поездки
    через Pydantic (FinalProgram) и выводит её в консоль.
    """
    ctx = PlannerContext(
        city=state["city"],
        dates=state["dates"],
        origin_city=state["origin_city"],
        search_context=state.get("search_context", ""),
    )
    rebuild_scope = state.get("rebuild_scope", "full")
    base_program = state.get("base_program")
    prefs_note = ""
    if ctx.search_context:
        prefs_note = f"\nУчти предпочтения: {ctx.search_context}\n"
    scope_note = finalize_extra_prompt(rebuild_scope, base_program)
    tickets_body = resolve_tickets_section(
        messages=state["messages"],
        base_program=base_program,
        origin_city=ctx.origin_city,
        destination_city=ctx.city,
        dates=ctx.dates,
        rebuild_scope=rebuild_scope,
    )
    route_feedback_ctx = None
    trip_id = state.get("trip_id")
    feedback_snapshot = state.get("route_feedback_snapshot")
    if feedback_snapshot:
        from models.routes import TripRouteCase
        from program.route_feedback import RouteFeedbackContext

        liked = tuple(
            TripRouteCase.model_validate(raw)
            for raw in feedback_snapshot.get("liked_cases") or []
        )
        route_feedback_ctx = RouteFeedbackContext(
            liked_cases=liked,
            llm_instructions=str(feedback_snapshot.get("llm_instructions") or ""),
            preferred_poi_ids=frozenset(
                feedback_snapshot.get("preferred_poi_ids") or []
            ),
            banned_poi_ids=frozenset(
                feedback_snapshot.get("banned_poi_ids") or []
            ),
        )
    elif (
        rebuild_scope in ("full", "routes", "events", "dining")
        and base_program
        and trip_id is not None
    ):
        from program.route_feedback import build_route_feedback_context

        route_feedback_ctx = build_route_feedback_context(
            base_program, int(trip_id), rebuild_scope=rebuild_scope
        )

    routes_instruction = (
        "- routes: РОВНО 3 пеших маршрута A/B/C разной длины. "
        "Только leisure poi_id из materials_digest; без вокзалов и аэропортов. "
        "A/B/C различаются протяжённостью (короткий/средний/длинный), не числом точек; "
        "насыщай маршрут местами из пула. narrative — название места. "
        "При уместности (набережная, два моста, компактный центр) укажи loop_route: true. "
        "maps_route_url оставь пустым — заполнит пост-процессор.\n"
    )
    if route_feedback_ctx and route_feedback_ctx.liked_cases and rebuild_scope == "routes":
        routes_instruction = (
            "- routes: РОВНО 3 НОВЫх пеших маршрута A/B/C (компактный/средний/длинный). "
            "Лайкнутые варианты сохранятся автоматически — не дублируй их poi_id. "
            "Только leisure poi_id из materials_digest. "
            "При уместности укажи loop_route: true. maps_route_url оставь пустым.\n"
            f"{route_feedback_ctx.llm_instructions}"
        )
    elif route_feedback_ctx and route_feedback_ctx.liked_cases:
        routes_instruction = (
            "- routes: РОВНО 3 пеших маршрута A/B/C разной длины. "
            "Ориентируйся на параметры лайкнутых вариантов ниже (длина, мотивы); "
            "poi_id выбирай из materials_digest — можно новые места похожего типа. "
            "При уместности укажи loop_route: true.\n"
            f"{route_feedback_ctx.llm_instructions}"
        )
    elif route_feedback_ctx:
        routes_instruction = (
            "- routes: РОВНО 3 пеших маршрута A/B/C разной длины. "
            "Учти оценки остановок ниже при выборе poi_id из materials_digest. "
            "При уместности укажи loop_route: true.\n"
            f"{route_feedback_ctx.llm_instructions}"
        )

    system = SystemMessage(
        content=(
            "Составь программу по ToolMessage (билеты уже готовы).\n"
            f"{routes_instruction}"
            "- lifehacks: 4–7 коротких советов, до 800 символов, без ссылок.\n"
            f"Город: {ctx.city}. Даты: {ctx.dates}. Вылет из: {ctx.origin_city}."
            f"{prefs_note}{scope_note}"
        )
    )
    human = HumanMessage(content=human_message_for_scope(rebuild_scope))

    llm_final = get_llm_final()
    trip_id = state.get("trip_id")
    finalize_messages = prepare_finalize_messages(
        state["messages"],
        rebuild_scope=rebuild_scope,
        trip_id=int(trip_id) if trip_id is not None else None,
    )
    draft: ProgramDraft = invoke_program_draft(
        llm_final,
        system=system,
        tool_messages=finalize_messages,
        human=human,
        state_messages=state["messages"],
        city=ctx.city,
        walking_area=ctx.search_context or "",
        trip_id=int(trip_id) if trip_id is not None else None,
    )
    draft_fields = draft.model_dump()
    prefs = state.get("preferences") or {}
    transport = str(prefs.get("transport_preference") or "mixed")
    pace = str(prefs.get("pace") or "moderate")
    if rebuild_scope in ("full", "routes", "events", "dining"):
        routes_program, routes_text = resolve_routes_program(
            state["messages"],
            draft_fields.get("routes"),
            base_program=base_program,
            transport=transport,
            pace=pace,
            expected_city=ctx.city,
            trip_id=int(trip_id) if trip_id is not None else None,
            dates=ctx.dates,
            rebuild_scope=rebuild_scope,
            route_feedback_snapshot=feedback_snapshot,
        )
        if trip_id is not None and rebuild_scope == "full":
            materials = load_route_materials(
                state["messages"],
                expected_city=ctx.city,
                trip_id=int(trip_id),
            )
            if materials is not None:
                from search.route_materials_store import persist_route_materials

                persist_route_materials(int(trip_id), materials, overwrite=True)
        draft_fields["routes"] = routes_program.model_dump()
        draft_fields["routes_text"] = routes_text
    if rebuild_scope in ("full", "lifehacks"):
        from agents.lifehacks_quality import clean_lifehacks_display

        draft_fields["lifehacks"] = clean_lifehacks_display(
            draft_fields.get("lifehacks", ""),
            city=ctx.city,
            walking_area=ctx.search_context or "",
            search_context=ctx.search_context or "",
        )

    full_draft = {**draft_fields, "tickets": tickets_body}
    merged = merge_program(base_program, full_draft, rebuild_scope)
    merged["tickets"] = tickets_body
    program = FinalProgram.model_validate(normalize_stored_program(merged))
    program_dump = program.model_dump()
    from agents.lifehacks_quality import clean_lifehacks_display

    program_dump["lifehacks"] = clean_lifehacks_display(
        program_dump.get("lifehacks", ""),
        city=ctx.city,
        walking_area=ctx.search_context or "",
        search_context=ctx.search_context or "",
    )
    if trip_id is not None:
        program_dump = repair_program_routes(
            program_dump,
            messages=state["messages"],
            trip_id=int(trip_id),
            city=ctx.city,
            dates=ctx.dates,
            base_program=base_program,
            transport=transport,
            pace=pace,
        )
    if trip_id is not None and rebuild_scope in ("full", "tickets"):
        from search.affiliate.wrap import wrap_tickets_markdown

        program_dump["tickets"] = wrap_tickets_markdown(
            str(program_dump.get("tickets", "")),
            int(trip_id),
        )
    program = FinalProgram.model_validate(program_dump)

    print_final_program(program)

    routes_body = program.routes_text or ""
    summary = (
        f"## Билеты\n{program.tickets}\n\n"
        f"## Маршруты\n{routes_body}\n\n"
        f"## Лайфхаки\n{program.lifehacks}"
    )
    final_message = AIMessage(content=summary)
    return {"messages": [final_message], "program": program_dump}


def critic_node(state: AgentState) -> dict[str, Any]:
    """Агент-critic: детерминированные проверки перед показом пользователю."""
    passed, notes = run_critic(state)
    print(f"  [critic] {notes}")
    result: dict[str, Any] = {"critic_passed": passed, "critic_notes": notes}
    if not passed:
        result["retry_count"] = state.get("retry_count", 0) + 1
    return result


def human_review_node(state: AgentState) -> dict[str, Any]:
    """Human-in-the-loop: утверждение программы y/n или отложенный review для API."""
    print("\n--- Проверка программы ---")
    if state.get("critic_notes"):
        print(f"Замечания critic: {state['critic_notes']}")

    if state.get("review_mode") == "deferred":
        if state.get("trip_id") is not None:
            update_trip_status(int(state["trip_id"]), "review")
        return {"approved": False}

    if state.get("review_mode") == "cli" and state.get("trip_id") and state.get("program"):
        from cli.feedback import offer_feedback_before_review
        from services import TripService

        offer_feedback_before_review(
            TripService(),
            int(state["trip_id"]),
            program_data=state["program"],
            scope=str(state.get("rebuild_scope", "full")),
        )

    if prompt_approve_program():
        print("✓ Программа утверждена.\n")
        if state.get("trip_id") is not None:
            update_trip_status(int(state["trip_id"]), "approved")
        return {"approved": True}

    action = prompt_reject_action()
    if action == "save_draft":
        if state.get("trip_id") is not None:
            update_trip_status(int(state["trip_id"]), "review")
        return {"approved": True}

    print("Повторная сборка по замечаниям...\n")
    result: dict[str, Any] = {
        "approved": False,
        "retry_count": state.get("retry_count", 0) + 1,
        "messages": [
            HumanMessage(
                content=(
                    "Пользователь не утвердил программу. "
                    "Пересобери слабые разделы, опираясь на digest."
                )
            )
        ],
    }
    if state.get("program"):
        result["base_program"] = state["program"]
    return result


def route_entry(state: AgentState) -> Literal["researcher", "writer"]:
    """Лайфхаки и пересбор маршрутов без POI-поиска — сразу writer."""
    scope = state.get("rebuild_scope", "full")
    if scope in ("lifehacks", "routes", "events", "dining"):
        return "writer"
    return "researcher"


def route_after_researcher(state: AgentState) -> Literal["executor", "writer"]:
    """Researcher: tool_calls → executor; иначе → writer."""
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "executor"
    return "writer"


def route_after_critic(state: AgentState) -> Literal["human_review", "researcher"]:
    """Critic: ok → HITL; иначе retry researcher (до 2 раз)."""
    if state.get("critic_passed"):
        return "human_review"
    if state.get("retry_count", 0) >= 2:
        print("  [critic] лимит повторов — передаём на утверждение пользователю.")
        return "human_review"
    return "researcher"


def route_after_human(state: AgentState) -> Literal["researcher", "__end__"]:
    if state.get("review_mode") == "deferred":
        return "__end__"
    if state.get("approved"):
        return "__end__"
    return "researcher"
