"""Узлы LangGraph: researcher → executor|writer, critic, human_review."""

from __future__ import annotations

from typing import Any, Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from agents.critic import run_critic
from agents.human_review import prompt_approve_program, prompt_reject_action
from agents.llm import get_llm_final, get_llm_with_tools
from agents.print_program import print_final_program
from db import log_tool_run, update_trip_status
from models.schemas import (
    ExecutorNodeOutput,
    FinalProgram,
    PlannerContext,
    PlannerNodeOutput,
)
from models.state import AgentState
from planning import (
    finalize_extra_prompt,
    human_message_for_scope,
    merge_program,
    planner_tools_hint,
)
from search.tool_logging import parse_tool_result
from search.tools import TOOL_MAP

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
        "Инструменты: tickets=самолёт+поезд+автобус, events=музеи (в одном районе), "
        "dining=restaurants_digest (много ссылок, рядом с музеями). "
        "Цены — только из digest, иначе «уточните на сайте» + ссылка.\n\n"
        "Обязанности:\n"
        "1. Билеты: самолёт, поезд (РЖД/Tutu), автобус (search_roundtrip_tickets).\n"
        "2. Музеи/афиша в пешой доступности (search_culture_events).\n"
        "3. Рестораны со ссылками рядом с музеями + транспорт (search_dining_and_transport).\n\n"
        f"{tools_hint}\n"
        f"Для билетов: origin_city={ctx.origin_city}, destination_city={ctx.city}, dates={ctx.dates}. "
        f"Для афиши и ресторанов: city={ctx.city}, dates={ctx.dates}."
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
    llm_with_tools = get_llm_with_tools(
        city=state.get("city", ""),
        llm_region=state.get("llm_region"),
    )
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
        args = call.get("args") or {}
        tool_call_id = call["id"]

        try:
            if name not in TOOL_MAP:
                raise KeyError(f"Неизвестный инструмент: {name}")
            result = TOOL_MAP[name].invoke(args)
            content = result if isinstance(result, str) else str(result)
        except Exception as exc:
            content = f"Ошибка выполнения инструмента {name}: {exc}"

        trip_id = state.get("trip_id")
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
    system = SystemMessage(
        content=(
            "Составь программу по ToolMessage. Строго раздели:\n"
            "- tickets: три блока со ссылками — самолёт, поезд (РЖД/Tutu), автобус "
            "(из search_roundtrip_tickets).\n"
            "- events: музеи/выставки/концерты, сгруппируй по району (пешком 10–15 мин "
            "между точками), из search_culture_events + walking_area.\n"
            "- dining: минимум 6–8 ресторанов/кафе со ссылками из restaurants_digest; "
            "у каждого укажи район и «рядом с …» (музей из events).\n"
            "- transport: метро/маршруты из transport_digest.\n"
            "- lifehacks: советы по пешим маршрутам «музей → обед → музей».\n"
            "Цены — только из digest; иначе «уточните на сайте» + ссылка.\n"
            f"Город: {ctx.city}. Даты: {ctx.dates}. Вылет из: {ctx.origin_city}."
            f"{prefs_note}{scope_note}"
        )
    )
    human = HumanMessage(content=human_message_for_scope(rebuild_scope))

    llm_final = get_llm_final(
        city=state.get("city", ""),
        llm_region=state.get("llm_region"),
    )
    draft: FinalProgram = llm_final.invoke([system, *state["messages"], human])
    merged = merge_program(base_program, draft.model_dump(), rebuild_scope)
    program = FinalProgram.model_validate(merged)

    print_final_program(program)

    summary = (
        f"## Билеты\n{program.tickets}\n\n"
        f"## Мероприятия\n{program.events}\n\n"
        f"## Питание\n{program.dining}\n\n"
        f"## Транспорт\n{program.transport}\n\n"
        f"## Лайфхаки\n{program.lifehacks}"
    )
    final_message = AIMessage(content=summary)
    return {"messages": [final_message], "program": program.model_dump()}


def critic_node(state: AgentState) -> dict[str, Any]:
    """Агент-critic: детерминированные проверки перед показом пользователю."""
    passed, notes = run_critic(state)
    print(f"  [critic] {notes}")
    result: dict[str, Any] = {"critic_passed": passed, "critic_notes": notes}
    if not passed:
        result["retry_count"] = state.get("retry_count", 0) + 1
    return result


def human_review_node(state: AgentState) -> dict[str, Any]:
    """Human-in-the-loop: утверждение программы y/n."""
    print("\n--- Проверка программы ---")
    if state.get("critic_notes"):
        print(f"Замечания critic: {state['critic_notes']}")

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
    return {
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


def route_entry(state: AgentState) -> Literal["researcher", "writer"]:
    """Лайфхаки без веб-поиска — сразу writer."""
    if state.get("rebuild_scope") == "lifehacks":
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
    if state.get("approved"):
        return "__end__"
    return "researcher"
