"""Pydantic-схемы инструментов и финальной программы."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, ToolMessage
from pydantic import BaseModel, Field

from models.tickets import TicketsSearchInput  # контракт билетов — models/tickets.py

PROGRAM_SECTION_KEYS = ("tickets", "events", "dining", "lifehacks")
_LEGACY_PROGRAM_KEYS = ("transport",)


class CultureEventsInput(BaseModel):
    """Параметры поиска культурных мероприятий и музеев."""

    city: str = Field(..., description="Город пребывания")
    dates: str = Field(..., description="Даты поездки")


class DiningInput(BaseModel):
    """Параметры поиска ресторанов и кафе."""

    city: str = Field(..., description="Город пребывания")
    dates: str = Field(..., description="Даты поездки")


# Обратная совместимость импортов
DiningTransportInput = DiningInput


class PlannerContext(BaseModel):
    """Контекст планировщика: город, даты, вылет и предпочтения опросника."""

    city: str
    dates: str
    origin_city: str
    search_context: str = ""


class ProgramDraft(BaseModel):
    """Секции программы от LLM (без билетов — их подставляет finalize из tool)."""

    events: str = Field(
        ...,
        description="Музеи, выставки, мероприятия (желательно в одном районе для прогулок)",
    )
    dining: str = Field(
        ...,
        description="Рестораны и кафе со ссылками, рядом с мероприятиями (пешая доступность)",
    )
    lifehacks: str = Field(..., description="Полезные лайфхаки для туриста")


class FinalProgram(BaseModel):
    """Структурированная культурная программа поездки."""

    tickets: str = Field(
        ...,
        description="Билеты туда-обратно: самолёт, поезд (РЖД), автобус — со ссылками",
    )
    events: str = Field(
        ...,
        description="Музеи, выставки, мероприятия (желательно в одном районе для прогулок)",
    )
    dining: str = Field(
        ...,
        description="Рестораны и кафе со ссылками, рядом с мероприятиями (пешая доступность)",
    )
    lifehacks: str = Field(..., description="Полезные лайфхаки для туриста")


def normalize_stored_program(data: dict[str, Any]) -> dict[str, Any]:
    """Убирает устаревшие ключи (например transport) из JSON в SQLite."""
    return {k: v for k, v in data.items() if k not in _LEGACY_PROGRAM_KEYS}


class PlannerNodeOutput(BaseModel):
    """Структурированный результат узла planner (для документирования контракта)."""

    message: AIMessage


class ExecutorNodeOutput(BaseModel):
    """Структурированный результат узла executor: список ответов инструментов."""

    tool_messages: list[ToolMessage]
