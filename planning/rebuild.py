"""Какие tools и поля программы затрагивает каждый rebuild_scope."""

from __future__ import annotations

from typing import Any, Literal

from models.schemas import normalize_stored_program

RebuildScope = Literal[
    "full",
    "tickets",
    "routes",
    "lifehacks",
    # legacy
    "events",
    "dining",
]

REBUILD_SCOPES: list[tuple[str, str]] = [
    ("full", "Всю программу"),
    ("tickets", "Только билеты (самолёт/поезд/автобус)"),
    ("routes", "Только маршруты"),
    ("lifehacks", "Только лайфхаки (без веб-поиска)"),
]

_SCOPE_TOOLS: dict[str, tuple[str, ...]] = {
    "full": (
        "search_roundtrip_tickets",
        "search_route_materials",
    ),
    "tickets": ("search_roundtrip_tickets",),
    "routes": (),
    "lifehacks": (),
    "events": (),
    "dining": (),
}

_SCOPE_FIELD: dict[str, str] = {
    "tickets": "tickets",
    "routes": "routes",
    "lifehacks": "lifehacks",
    "events": "routes",
    "dining": "routes",
}

_LEGACY_TOOL_ALIASES: dict[str, str] = {
    "search_dining_and_transport": "search_route_materials",
    "search_culture_events": "search_route_materials",
    "search_dining": "search_route_materials",
}


def resolve_tool_name(name: str) -> str:
    """Каноническое имя инструмента (для executor и critic)."""
    return _LEGACY_TOOL_ALIASES.get(name, name)


def tool_call_satisfied(required: str, tools_done: set[str]) -> bool:
    if required in tools_done:
        return True
    for legacy, canonical in _LEGACY_TOOL_ALIASES.items():
        if canonical == required and legacy in tools_done:
            return True
    return False


def required_tools_for_scope(scope: str) -> list[str]:
    """Имена @tool, которые нужно вызвать для данного scope."""
    return list(_SCOPE_TOOLS.get(scope, _SCOPE_TOOLS["full"]))


def scope_field(scope: str) -> str | None:
    """Поле FinalProgram для частичного merge или None для full."""
    if scope == "full":
        return None
    return _SCOPE_FIELD.get(scope)


def merge_program(
    base: dict[str, Any] | None,
    updated: dict[str, Any],
    scope: str,
) -> dict[str, Any]:
    """Подставляет один раздел из updated в сохранённую программу."""
    updated = normalize_stored_program(updated)
    if scope == "full" or not base:
        return updated
    field = scope_field(scope)
    if not field:
        return updated
    merged = normalize_stored_program(dict(base))
    if field == "routes":
        merged["routes"] = updated.get("routes", merged.get("routes"))
        merged["routes_text"] = updated.get("routes_text", merged.get("routes_text", ""))
    else:
        merged[field] = updated.get(field, merged.get(field, ""))
    return merged


def planner_tools_hint(scope: str) -> str:
    """Инструкция planner: какие tools вызывать."""
    tools = required_tools_for_scope(scope)
    if scope == "lifehacks":
        return "Новый веб-поиск не нужен. Сразу ответь без tool_calls."
    if scope in ("routes", "events", "dining"):
        return (
            f"Режим частичной пересборки ({scope}). "
            "Новый поиск POI не нужен — пул уже в базе. "
            "Сразу ответь без tool_calls."
        )
    if scope == "full":
        return (
            "Сначала вызови оба инструмента (билеты и route_materials), если их нет в истории. "
            "Когда оба выполнены — ответь кратко без tool_calls."
        )
    names = ", ".join(tools)
    return (
        f"Режим частичной пересборки ({scope}). "
        f"Вызови ТОЛЬКО: {names}. "
        "После успешного поиска — ответь кратко без новых tool_calls."
    )


def human_message_for_scope(scope: str) -> str:
    """Стартовое сообщение пользователя для графа."""
    messages = {
        "full": "Составь культурную программу поездки с тремя вариантами маршрута.",
        "tickets": (
            "Пересобери только раздел билетов (самолёт, поезд, автобус). "
            "Используй search_roundtrip_tickets."
        ),
        "routes": (
            "Пересобери маршруты: сгенерируй 3 новых варианта из сохранённого пула POI. "
            "Лайкнутые маршруты сохранятся автоматически. "
            "Новый search_route_materials не вызывай."
        ),
        "events": (
            "Пересобери маршруты из сохранённого пула POI. "
            "Новый search_route_materials не вызывай."
        ),
        "dining": (
            "Пересобери маршруты из сохранённого пула POI. "
            "Новый search_route_materials не вызывай."
        ),
        "lifehacks": (
            "Обнови только лайфхаки по текущей программе поездки. Без нового поиска."
        ),
    }
    return messages.get(scope, messages["full"])


def finalize_extra_prompt(scope: str, base_program: dict[str, Any] | None) -> str:
    """Дополнение к системному промпту finalize при частичной пересборке."""
    if scope == "full" or not base_program:
        return ""
    field = scope_field(scope)
    if not field:
        return ""
    if scope == "lifehacks":
        return (
            "\nРежим: обнови ТОЛЬКО поле lifehacks. "
            "Остальные разделы возьми из текущей программы без изменений.\n"
            f"Текущие билеты: {str(base_program.get('tickets', ''))[:500]}...\n"
            f"Текущие маршруты: {str(base_program.get('routes_text', ''))[:500]}...\n"
        )
    if scope in ("routes", "events", "dining"):
        return (
            f"\nРежим: пересобери ТОЛЬКО маршруты ({scope}) из сохранённого пула POI в базе. "
            "Новые места не придумывай — только poi_id из materials_digest.\n"
            f"{_format_base_sections(base_program, exclude='routes')}\n"
        )
    labels = {
        "tickets": "билеты",
        "routes": "маршруты",
    }
    label = labels.get(field, field)
    return (
        f"\nРежим частичной пересборки: заполни ТОЛЬКО раздел «{label}» ({field}). "
        "Остальные поля скопируй из текущей программы:\n"
        f"{_format_base_sections(base_program, exclude=field)}\n"
    )


def _format_base_sections(base: dict[str, Any], *, exclude: str) -> str:
    parts: list[str] = []
    for key, title in (
        ("tickets", "Билеты"),
        ("routes_text", "Маршруты"),
        ("lifehacks", "Лайфхаки"),
    ):
        if key == exclude or (exclude == "routes" and key == "routes_text"):
            continue
        parts.append(f"--- {title} ({key}) ---\n{base.get(key, '')}")
    return "\n\n".join(parts)
