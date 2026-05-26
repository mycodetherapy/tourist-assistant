"""Какие tools и поля программы затрагивает каждый rebuild_scope."""

from __future__ import annotations

from typing import Any, Literal

RebuildScope = Literal[
    "full",
    "tickets",
    "events",
    "dining",
    "transport",
    "lifehacks",
]

REBUILD_SCOPES: list[tuple[str, str]] = [
    ("full", "Всю программу"),
    ("tickets", "Только билеты (✈️ 🚂 🚌)"),
    ("events", "Только мероприятия"),
    ("dining", "Только питание"),
    ("transport", "Только транспорт в городе"),
    ("lifehacks", "Только лайфхаки (без веб-поиска)"),
]

_SCOPE_TOOLS: dict[str, tuple[str, ...]] = {
    "full": (
        "search_roundtrip_tickets",
        "search_culture_events",
        "search_dining_and_transport",
    ),
    "tickets": ("search_roundtrip_tickets",),
    "events": ("search_culture_events",),
    "dining": ("search_dining_and_transport",),
    "transport": ("search_dining_and_transport",),
    "lifehacks": (),
}

_SCOPE_FIELD: dict[str, str] = {
    "tickets": "tickets",
    "events": "events",
    "dining": "dining",
    "transport": "transport",
    "lifehacks": "lifehacks",
}


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
    if scope == "full" or not base:
        return updated
    field = scope_field(scope)
    if not field:
        return updated
    merged = dict(base)
    merged[field] = updated.get(field, merged.get(field, ""))
    return merged


def planner_tools_hint(scope: str) -> str:
    """Инструкция planner: какие tools вызывать."""
    tools = required_tools_for_scope(scope)
    if scope == "lifehacks":
        return "Новый веб-поиск не нужен. Сразу ответь без tool_calls."
    if scope == "full":
        return (
            "Сначала вызови ВСЕ три инструмента, если их результатов ещё нет в истории. "
            "Когда все три поиска выполнены — ответь кратко без вызова инструментов."
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
        "full": "Составь культурную программу поездки.",
        "tickets": (
            "Пересобери только раздел билетов (самолёт, поезд, автобус). "
            "Используй search_roundtrip_tickets."
        ),
        "events": (
            "Пересобери только мероприятия и музеи. Используй search_culture_events."
        ),
        "dining": (
            "Пересобери только питание (рестораны со ссылками). "
            "Используй search_dining_and_transport."
        ),
        "transport": (
            "Пересобери только городской транспорт. "
            "Используй search_dining_and_transport (transport_digest)."
        ),
        "lifehacks": (
            "Обнови только лайфхаки по текущей программе поездки "
            "(маршруты «музей → обед», советы по транспорту). Без нового поиска."
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
            "Остальные разделы возьми из текущей программы ниже без изменений.\n"
            f"Текущие билеты (не менять): {base_program.get('tickets', '')[:500]}...\n"
            f"Текущие мероприятия: {base_program.get('events', '')[:500]}...\n"
            f"Текущее питание: {base_program.get('dining', '')[:500]}...\n"
        )
    labels = {
        "tickets": "билеты",
        "events": "мероприятия",
        "dining": "питание",
        "transport": "транспорт",
    }
    label = labels.get(field, field)
    return (
        f"\nРежим частичной пересборки: заполни ТОЛЬКО раздел «{label}» ({field}). "
        "Остальные поля в ответе скопируй дословно из текущей программы:\n"
        f"{_format_base_sections(base_program, exclude=field)}\n"
    )


def _format_base_sections(base: dict[str, Any], *, exclude: str) -> str:
    parts: list[str] = []
    for key, title in (
        ("tickets", "Билеты"),
        ("events", "Мероприятия"),
        ("dining", "Питание"),
        ("transport", "Транспорт"),
        ("lifehacks", "Лайфхаки"),
    ):
        if key == exclude:
            continue
        parts.append(f"--- {title} ({key}) ---\n{base.get(key, '')}")
    return "\n\n".join(parts)
