"""Pydantic-схемы инструментов и финальной программы."""

from __future__ import annotations

from langchain_core.messages import AIMessage, ToolMessage
from pydantic import BaseModel, Field


class TicketsSearchInput(BaseModel):
    """Параметры поиска билетов туда-обратно (самолёт, поезд, автобус)."""

    origin_city: str = Field(..., description="Город отправления")
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
    """Контекст планировщика: город, даты, вылет и предпочтения опросника."""

    city: str
    dates: str
    origin_city: str
    search_context: str = ""


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
    transport: str = Field(..., description="Транспортная логистика в городе")
    lifehacks: str = Field(..., description="Полезные лайфхаки для туриста")


class PlannerNodeOutput(BaseModel):
    """Структурированный результат узла planner (для документирования контракта)."""

    message: AIMessage


class ExecutorNodeOutput(BaseModel):
    """Структурированный результат узла executor: список ответов инструментов."""

    tool_messages: list[ToolMessage]
