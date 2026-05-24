"""
Туристический ассистент на LangGraph.

Установка зависимостей:
    pip install "langgraph>=0.2" "langchain>=0.3" langchain-openai langchain-core python-dotenv pydantic

Переменные окружения (.env):
    OPENAI_API_KEY=sk-...
    PROXY_BASE_URL=https://openai.api.proxyapi.ru/v1

Запуск:
    python main.py
"""

from __future__ import annotations

import json
import os
import re
from typing import Annotated, Any, Literal, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field, ValidationError

# Загружаем переменные окружения из .env (ключи не хардкодим)
load_dotenv()

# ---------------------------------------------------------------------------
# Pydantic-модели: аргументы инструментов и финальная программа поездки
# ---------------------------------------------------------------------------


class TicketsSearchInput(BaseModel):
    """Параметры поиска авиабилетов туда-обратно."""

    origin_city: str = Field(..., description="Город вылета")
    destination_city: str = Field(..., description="Город назначения")
    dates: str = Field(..., description="Даты поездки в свободной форме")


class CultureEventsInput(BaseModel):
    """Параметры поиска культурных мероприятий и музеев."""

    city: str = Field(..., description="Город пребывания")
    dates: str = Field(..., description="Даты поездки")


class DiningTransportInput(BaseModel):
    """Параметры поиска ресторанов и городского транспорта."""

    city: str = Field(..., description="Город пребывания")
    dates: str = Field(..., description="Даты поездки")


class PlannerContext(BaseModel):
    """Контекст планировщика: город и даты поездки."""

    city: str
    dates: str


class FinalProgram(BaseModel):
    """Структурированная культурная программа поездки."""

    tickets: str = Field(..., description="Билеты туда-обратно")
    events: str = Field(..., description="Музеи, выставки, мероприятия")
    dining: str = Field(..., description="Рестораны и кафе")
    transport: str = Field(..., description="Транспортная логистика в городе")
    lifehacks: str = Field(..., description="Полезные лайфхаки для туриста")


class PlannerNodeOutput(BaseModel):
    """Структурированный результат узла planner (для документирования контракта)."""

    message: AIMessage


class ExecutorNodeOutput(BaseModel):
    """Структурированный результат узла executor: список ответов инструментов."""

    tool_messages: list[ToolMessage]


# ---------------------------------------------------------------------------
# Валидация пользовательского ввода (защита от prompt-injection)
# ---------------------------------------------------------------------------

_MAX_LENGTHS: dict[str, int] = {
    "city": 500,
    "dates": 500,
    "message": 2000,
}

_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"ignore\s+(all\s+)?(previous|prior)\s+instructions",
        r"disregard\s+(all\s+)?(previous|prior)",
        r"system\s*:",
        r"assistant\s*:",
        r"<\|",
        r"\{\{",
        r"```",
        r"jailbreak",
        r"you\s+are\s+now",
        r"новые\s+инструкции",
        r"забудь\s+(все|предыдущ)",
        r"игнорируй\s+(все|предыдущ)",
    )
]


def sanitize_and_validate(text: str, field_name: str) -> str:
    """
    Очищает и проверяет пользовательский ввод на инъекции и чрезмерную длину.
    Возвращает нормализованную строку или выбрасывает ValueError.
    """
    cleaned = text.strip()
    if not cleaned:
        raise ValueError(f"Поле «{field_name}» не может быть пустым.")

    max_len = _MAX_LENGTHS.get(field_name, 2000)
    if len(cleaned) > max_len:
        raise ValueError(
            f"Поле «{field_name}» слишком длинное (максимум {max_len} символов)."
        )

    for pattern in _INJECTION_PATTERNS:
        if pattern.search(cleaned):
            raise ValueError(
                f"Поле «{field_name}» содержит подозрительные конструкции и отклонено."
            )

    return cleaned


# ---------------------------------------------------------------------------
# Mock-инструменты (имитация российских сервисов)
# ---------------------------------------------------------------------------


@tool
def search_roundtrip_tickets(
    origin_city: str,
    destination_city: str,
    dates: str,
) -> str:
    """
    Поиск авиабилетов туда-обратно через Aviasales / Яндекс.Путешествия.
    Возвращает JSON с вариантами рейсов и ценами.
    """
    try:
        params = TicketsSearchInput(
            origin_city=origin_city,
            destination_city=destination_city,
            dates=dates,
        )
    except ValidationError as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)

    # TODO: заменить на requests.get(...)
    # Пример: GET https://api.travel.yandex.ru/v1/flights?from={origin}&to={dest}&dates={dates}
    # Или Aviasales Partner API: https://www.aviasales.ru/api/...

    mock_response = {
        "source": "Aviasales / Яндекс.Путешествия (mock)",
        "query": params.model_dump(),
        "flights": [
            {
                "airline": "Аэрофлот",
                "outbound": f"{params.origin_city} → {params.destination_city}, утро",
                "return": f"{params.destination_city} → {params.origin_city}, вечер",
                "price_rub": 18400,
                "duration_hours": 1.5,
                "link": "https://www.aviasales.ru/search/mock-kazan",
            },
            {
                "airline": "Победа",
                "outbound": f"{params.origin_city} → {params.destination_city}, день",
                "return": f"{params.destination_city} → {params.origin_city}, день",
                "price_rub": 12900,
                "duration_hours": 1.5,
                "link": "https://travel.yandex.ru/flights/mock-kazan",
            },
        ],
        "tip": "Бронируйте за 3–4 недели до поездки для лучшей цены.",
    }
    return json.dumps(mock_response, ensure_ascii=False, indent=2)


@tool
def search_culture_events(city: str, dates: str) -> str:
    """
    Поиск музеев, выставок и мероприятий через Афиша / Кассир.ру.
    Возвращает JSON с культурной афишей и режимом работы.
    """
    try:
        params = CultureEventsInput(city=city, dates=dates)
    except ValidationError as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)

    # TODO: заменить на requests.get(...)
    # Пример Афиша API: GET https://api.afisha.ru/v1/events?city={city}&date_from=...

    mock_response = {
        "source": "Афиша / Кассир.ру (mock)",
        "query": params.model_dump(),
        "events": [
            {
                "name": "Государственный музей изобразительных искусств",
                "type": "музей",
                "schedule": "Вт–Вс 10:00–18:00, Пн — выходной",
                "ticket_rub": 400,
                "rating": 4.8,
                "link": "https://www.afisha.ru/kazan/museum/mock-gmii",
            },
            {
                "name": "Выставка «Казань: 1000 лет истории»",
                "type": "выставка",
                "schedule": "Ежедневно 11:00–20:00",
                "ticket_rub": 350,
                "rating": 4.7,
                "link": "https://kassir.ru/kazan/exhibition/mock-1000",
            },
            {
                "name": "Концерт в Казанской филармонии",
                "type": "концерт",
                "schedule": f"В период {params.dates}, 19:00",
                "ticket_rub": 1200,
                "rating": 4.9,
                "link": "https://www.afisha.ru/kazan/concert/mock-philharmonic",
            },
        ],
    }
    return json.dumps(mock_response, ensure_ascii=False, indent=2)


@tool
def search_dining_and_transport(city: str, dates: str) -> str:
    """
    Поиск ресторанов с высоким рейтингом и транспортной логистики через 2GIS / Яндекс.Карты.
    Возвращает JSON с заведениями и маршрутами.
    """
    try:
        params = DiningTransportInput(city=city, dates=dates)
    except ValidationError as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)

    # TODO: заменить на requests.get(...)
    # Пример 2GIS: GET https://catalog.api.2gis.com/3.0/items?q=рестораны&city={city}
    # Яндекс.Карты: https://api-maps.yandex.ru/services/route/...

    mock_response = {
        "source": "2GIS / Яндекс.Карты (mock)",
        "query": params.model_dump(),
        "restaurants": [
            {
                "name": "Тубэтей",
                "cuisine": "татарская",
                "rating": 4.9,
                "price_level": "₽₽",
                "address": "ул. Баумана, 19/8",
                "link": "https://2gis.ru/kazan/firm/mock-tubetey",
            },
            {
                "name": "Бульвар",
                "cuisine": "европейская",
                "rating": 4.8,
                "price_level": "₽₽₽",
                "address": "ул. Профсоюзная, 1",
                "link": "https://yandex.ru/maps/org/mock-bulvar",
            },
        ],
        "transport": {
            "metro_lines": ["Центральная (красная)", "Северная (зелёная)"],
            "day_pass_rub": 120,
            "routes": [
                "Аэропорт → Центр: метро + автобус №97, ~40 мин",
                "Кремль → ВДНХ: метро 2 остановки + пешком 10 мин",
                "Вокзал → Баумана: метро 15 мин или такси ~250 ₽",
            ],
            "apps": ["Яндекс.Метро", "2GIS", "Яндекс.Go"],
        },
    }
    return json.dumps(mock_response, ensure_ascii=False, indent=2)


# Список всех инструментов и словарь для быстрого доступа в executor
TOOLS = [
    search_roundtrip_tickets,
    search_culture_events,
    search_dining_and_transport,
]
TOOL_MAP: dict[str, Any] = {t.name: t for t in TOOLS}

# ---------------------------------------------------------------------------
# LLM (ProxyAPI + gpt-4o-mini)
# ---------------------------------------------------------------------------

llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.2,
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("PROXY_BASE_URL", "https://openai.api.proxyapi.ru/v1"),
)

llm_with_tools = llm.bind_tools(TOOLS)
llm_final = llm.with_structured_output(FinalProgram)

# ---------------------------------------------------------------------------
# State графа LangGraph
# ---------------------------------------------------------------------------


class AgentState(TypedDict):
    """Состояние агента: город, даты и история сообщений."""

    city: str
    dates: str
    messages: Annotated[list[AnyMessage], add_messages]


# ---------------------------------------------------------------------------
# Узлы графа
# ---------------------------------------------------------------------------


def _build_planner_system_prompt(ctx: PlannerContext) -> str:
    """Формирует системный промпт для узла planner."""
    return (
        "Ты — туристический ассистент. Составляешь культурную программу поездки.\n"
        f"Город: {ctx.city}. Даты: {ctx.dates}.\n\n"
        "Обязанности:\n"
        "1. Билеты туда-обратно (search_roundtrip_tickets).\n"
        "2. Музеи, выставки, мероприятия с режимом работы (search_culture_events).\n"
        "3. Рестораны/кафе с высоким рейтингом и транспорт (search_dining_and_transport).\n\n"
        "Сначала вызови ВСЕ три инструмента, если данных ещё нет в истории. "
        "Для билетов укажи origin_city (город вылета, по умолчанию Москва, если не указан) "
        f"и destination_city={ctx.city}. "
        "Когда все данные собраны — ответь пользователю кратким текстом без вызова инструментов."
    )


def planner_node(state: AgentState) -> dict[str, list[AnyMessage]]:
    """
    Узел планировщика: LLM анализирует запрос и формирует tool_calls
    для сбора данных или финальный ответ без инструментов.
    """
    ctx = PlannerContext(city=state["city"], dates=state["dates"])
    system = SystemMessage(content=_build_planner_system_prompt(ctx))
    response: AIMessage = llm_with_tools.invoke([system, *state["messages"]])

    # Структурированный контракт выхода (документируем через Pydantic)
    PlannerNodeOutput(message=response)

    return {"messages": [response]}


def executor_node(state: AgentState) -> dict[str, list[ToolMessage]]:
    """
    Узел исполнителя: выполняет tool_calls из последнего AIMessage
    и возвращает ToolMessage в State. Ошибки инструментов не роняют граф.
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

        tool_messages.append(
            ToolMessage(content=content, tool_call_id=tool_call_id, name=name)
        )

    ExecutorNodeOutput(tool_messages=tool_messages)
    return {"messages": tool_messages}


def finalize_node(state: AgentState) -> dict[str, list[AnyMessage]]:
    """
    Финальный узел: формирует структурированную программу поездки
    через Pydantic (FinalProgram) и выводит её в консоль.
    """
    ctx = PlannerContext(city=state["city"], dates=state["dates"])
    system = SystemMessage(
        content=(
            "На основе собранных данных инструментов и переписки составь "
            "полную культурную программу поездки. Заполни все пять разделов "
            "подробно, на русском языке, с конкретными названиями и советами.\n"
            f"Город: {ctx.city}. Даты: {ctx.dates}."
        )
    )
    human = HumanMessage(
        content="Сформируй итоговую программу: билеты, мероприятия, питание, транспорт, лайфхаки."
    )

    program: FinalProgram = llm_final.invoke([system, *state["messages"], human])

    _print_final_program(program)

    summary = (
        f"## Билеты\n{program.tickets}\n\n"
        f"## Мероприятия\n{program.events}\n\n"
        f"## Питание\n{program.dining}\n\n"
        f"## Транспорт\n{program.transport}\n\n"
        f"## Лайфхаки\n{program.lifehacks}"
    )
    final_message = AIMessage(content=summary)
    return {"messages": [final_message]}


def _print_final_program(program: FinalProgram) -> None:
    """Печатает финальную программу в консоль по разделам."""
    sections = [
        ("Билеты", program.tickets),
        ("Мероприятия", program.events),
        ("Питание", program.dining),
        ("Транспорт", program.transport),
        ("Лайфхаки", program.lifehacks),
    ]
    print("\n" + "=" * 60)
    print("КУЛЬТУРНАЯ ПРОГРАММА ПОЕЗДКИ")
    print("=" * 60)
    for title, body in sections:
        print(f"\n--- {title} ---\n")
        print(body)
    print("\n" + "=" * 60)


def route_after_planner(state: AgentState) -> Literal["executor", "finalize"]:
    """
    Условное ребро: если в последнем сообщении есть tool_calls — в executor,
    иначе — к финальному формированию ответа.
    """
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "executor"
    return "finalize"


# ---------------------------------------------------------------------------
# Сборка и компиляция графа LangGraph
# ---------------------------------------------------------------------------

workflow = StateGraph(AgentState)

workflow.add_node("planner", planner_node)
workflow.add_node("executor", executor_node)
workflow.add_node("finalize", finalize_node)

workflow.add_edge(START, "planner")
workflow.add_conditional_edges(
    "planner",
    route_after_planner,
    {"executor": "executor", "finalize": "finalize"},
)
workflow.add_edge("executor", "planner")
workflow.add_edge("finalize", END)

app = workflow.compile()


# ---------------------------------------------------------------------------
# Точка входа
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    city_raw = "Казань"
    dates_raw = "15-18 июля 2026"
    user_message_raw = "Составь культурную программу"

    if not os.getenv("OPENAI_API_KEY"):
        print(
            "Ошибка: не задан OPENAI_API_KEY. "
            "Создайте файл .env с OPENAI_API_KEY=... и при необходимости PROXY_BASE_URL."
        )
        raise SystemExit(1)

    try:
        city = sanitize_and_validate(city_raw, "city")
        dates = sanitize_and_validate(dates_raw, "dates")
        user_message = sanitize_and_validate(user_message_raw, "message")
    except ValueError as exc:
        print(f"Ошибка валидации входа: {exc}")
        raise SystemExit(1) from exc

    initial_state: AgentState = {
        "city": city,
        "dates": dates,
        "messages": [HumanMessage(content=user_message)],
    }

    print(f"Запуск ассистента: {city}, {dates}")
    print("Сбор данных через инструменты и формирование программы...\n")

    try:
        app.invoke(initial_state)
    except Exception as exc:
        print(f"Ошибка выполнения графа: {exc}")
        raise SystemExit(1) from exc
