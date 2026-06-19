"""Pydantic-схемы инструментов и финальной программы."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, ToolMessage
from pydantic import BaseModel, Field, model_validator

from models.routes import RouteProgram

_LEGACY_PROGRAM_KEYS = ("transport",)


class RouteMaterialsInput(BaseModel):
    """Параметры поиска пула мест для маршрутов."""

    city: str = Field(..., description="Город пребывания")
    dates: str = Field(..., description="Даты поездки")


class PlannerContext(BaseModel):
    """Контекст планировщика: город, даты, вылет и предпочтения опросника."""

    city: str
    dates: str
    origin_city: str
    search_context: str = ""


class RoutesDraft(BaseModel):
    """Только маршруты от LLM (факт о городе — отдельно, асинхронно)."""

    routes: RouteProgram = Field(
        ...,
        description="Ровно 3 варианта маршрута A/B/C из poi_id пула materials",
    )


class ProgramDraft(RoutesDraft):
    """Обратная совместимость: опциональный lifehacks."""

    lifehacks: str = Field(default="", description="Legacy; writer не заполняет")


class FinalProgram(BaseModel):
    """Структурированный результат построения маршрутов поездки."""

    tickets: str = Field(
        default="",
        description="Legacy: билеты (не используется в routes-only MVP)",
    )
    routes: RouteProgram | dict[str, Any] | None = Field(
        default=None,
        description="Три варианта маршрута на всю поездку",
    )
    routes_text: str = Field(default="", description="Markdown-представление маршрутов")
    lifehacks: str = Field(
        default="",
        description="Факт о городе (legacy ключ API; async при city_fact_status=pending)",
    )
    events: str = Field(default="", description="Legacy: мероприятия")
    dining: str = Field(default="", description="Legacy: питание")

    @model_validator(mode="before")
    @classmethod
    def coerce_routes(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        raw = data.get("routes")
        if isinstance(raw, dict) and raw.get("cases") is not None:
            try:
                data["routes"] = RouteProgram.model_validate(raw).model_dump()
            except Exception:
                pass
        return data

    def routes_model(self) -> RouteProgram | None:
        if self.routes is None:
            return None
        if isinstance(self.routes, RouteProgram):
            return self.routes
        if isinstance(self.routes, dict):
            try:
                return RouteProgram.model_validate(self.routes)
            except Exception:
                return None
        return None


def normalize_stored_program(data: dict[str, Any]) -> dict[str, Any]:
    """Убирает устаревшие ключи (например transport) из JSON в SQLite."""
    return {k: v for k, v in data.items() if k not in _LEGACY_PROGRAM_KEYS}


def is_legacy_program(data: dict[str, Any]) -> bool:
    return bool(data.get("events") or data.get("dining")) and not data.get("routes")


class PlannerNodeOutput(BaseModel):
    """Структурированный результат узла planner (для документирования контракта)."""

    message: AIMessage


class ExecutorNodeOutput(BaseModel):
    """Структурированный результат узла executor: список ответов инструментов."""

    tool_messages: list[ToolMessage]
