"""Какие tools и поля программы затрагивает каждый rebuild_scope."""

from __future__ import annotations

from typing import Any, Literal

from models.schemas import normalize_stored_program

RebuildScope = Literal[
    "full",
    "routes",
]

REBUILD_SCOPES: list[tuple[str, str]] = [
    ("routes", "Пересобрать маршруты (по текущему пулу)"),
    ("full", "Глубокий пересбор (обновить источники)"),
]

_SCOPE_TOOLS: dict[str, tuple[str, ...]] = {
    "full": ("search_route_materials",),
    "routes": (),
}

_SCOPE_FIELD: dict[str, str] = {
    "routes": "routes",
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
    return list(_SCOPE_TOOLS.get(scope, _SCOPE_TOOLS["routes"]))


def scope_field(scope: str) -> str | None:
    """Поле FinalProgram для частичного merge или None для full."""
    if scope == "full":
        return None
    return "routes"


def merge_program(
    base: dict[str, Any] | None,
    updated: dict[str, Any],
    scope: str,
) -> dict[str, Any]:
    """Подставляет один раздел из updated в сохранённую программу."""
    updated = normalize_stored_program(updated)
    if not base:
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
    if scope == "routes":
        return (
            "Режим частичного пересбора маршрутов. Используй уже сохранённый пул POI "
            "и не вызывай новый поиск источников. Ответь без tool_calls."
        )
    return (
        "Режим глубокого пересбора. Вызови search_route_materials один раз "
        "для обновления пула POI."
    )


def human_message_for_scope(scope: str) -> str:
    """Стартовое сообщение пользователя для графа."""
    messages = {
        "full": (
            "Сделай глубокий пересбор: сначала обнови пул POI через search_route_materials, "
            "затем собери 3 маршрута и обнови лайфхаки."
        ),
        "routes": (
            "Пересобери маршруты: сгенерируй 3 новых варианта из уже сохранённого пула POI. "
            "Новый поиск источников не делай. Лайфхаки обнови автоматически по новым маршрутам."
        ),
    }
    return messages.get(scope, messages["full"])


def finalize_extra_prompt(scope: str, base_program: dict[str, Any] | None) -> str:
    """Дополнение к системному промпту finalize при частичной пересборке."""
    if scope == "full":
        return ""
    if not base_program:
        return ""
    field = scope_field(scope)
    if not field:
        return ""
    if scope == "routes":
        return (
            f"\nРежим: пересобери маршруты ({scope}) из сохранённого пула POI в базе. "
            "Новые места не придумывай — только poi_id из materials_digest.\n"
            f"{_format_base_sections(base_program, exclude='routes')}\n"
        )
    return ""


def _format_base_sections(base: dict[str, Any], *, exclude: str) -> str:
    parts: list[str] = []
    for key, title in (
        ("routes_text", "Маршруты"),
        ("lifehacks", "Лайфхаки"),
    ):
        if key == exclude or (exclude == "routes" and key == "routes_text"):
            continue
        parts.append(f"--- {title} ({key}) ---\n{base.get(key, '')}")
    return "\n\n".join(parts)
