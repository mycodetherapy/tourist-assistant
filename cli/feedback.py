"""CLI: оценка пунктов программы (👍/👎)."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from program.parse_items import VOTABLE_SECTIONS, VotableSectionKey
from services.trip_service import ItemVote, ProgramView, TripService

_SECTION_TITLES: dict[VotableSectionKey, str] = {
    "routes": "Маршруты",
    "route_stops": "Остановки маршрута",
    "events": "Мероприятия",
    "dining": "Питание",
    "lifehacks": "Лайфхаки",
}

_CLI_VOTABLE_SECTIONS: tuple[VotableSectionKey, ...] = tuple(
    s for s in VOTABLE_SECTIONS if s != "route_stops"
)

_VOTE_MARK: dict[ItemVote | None, str] = {1: "👍", -1: "👎", None: "—"}

_YES = frozenset({"y", "yes", "д", "да"})


def _normalize_line(raw: str) -> str:
    return unicodedata.normalize("NFKC", raw.strip().lower()).replace("ё", "е")


def _truncate(text: str, limit: int = 100) -> str:
    flat = re.sub(r"\s+", " ", text.strip())
    if len(flat) <= limit:
        return flat
    return flat[: limit - 1] + "…"


def _load_view(
    service: TripService,
    trip_id: int,
    *,
    program_data: dict[str, Any] | None = None,
    scope: str = "full",
) -> ProgramView | None:
    if program_data is not None:
        return service.build_program_view(
            trip_id,
            program_data,
            scope=scope,
            approved=False,
        )
    return service.get_program_view(trip_id)


def print_votable_sections(view: ProgramView) -> None:
    """Печатает голосуемые секции с текущими оценками."""
    print(f"\n--- Программа v{view.version} ({view.scope}) — оценки ---")
    tickets = view.sections["tickets"]
    print("\n--- Билеты ---")
    print(tickets.intro or "(пусто)")
    print("(голосование недоступно для билетов)")
    for section_key in _CLI_VOTABLE_SECTIONS:
        section = view.sections.get(section_key)
        if section is None:
            continue
        print(f"\n--- {_SECTION_TITLES[section_key]} ---")
        if section.intro:
            print(section.intro)
        if not section.items:
            print("  (нет пунктов)")
            continue
        for item in section.items:
            mark = _VOTE_MARK[item.vote]
            print(f"  [{item.index}] {_truncate(item.text)}  {mark}")


def _parse_vote_command(raw: str) -> tuple[int, ItemVote | None] | None:
    parts = raw.split()
    if len(parts) != 2:
        return None
    try:
        index = int(parts[0])
    except ValueError:
        return None
    token = _normalize_line(parts[1])
    if token in {"+", "1", "+1"}:
        return index, 1
    if token in {"-", "-1"}:
        return index, -1
    if token in {"0", "снять", "x"}:
        return index, None
    return None


def _vote_in_section(
    service: TripService,
    trip_id: int,
    section_key: VotableSectionKey,
    *,
    program_data: dict[str, Any] | None = None,
    scope: str = "full",
) -> None:
    while True:
        view = _load_view(service, trip_id, program_data=program_data, scope=scope)
        if view is None:
            print("Программа не найдена.")
            return
        section = view.sections[section_key]
        print(f"\n--- {_SECTION_TITLES[section_key]} ---")
        if section.intro:
            print(section.intro)
        if not section.items:
            print("  (нет пунктов)")
            input("Enter — назад: ")
            return
        for item in section.items:
            mark = _VOTE_MARK[item.vote]
            print(f"  [{item.index}] {_truncate(item.text)}  {mark}")
        print("Команды: <номер> + | <номер> - | <номер> 0 (снять) | Enter (назад)")
        raw = input("> ").strip()
        if not raw:
            return
        parsed = _parse_vote_command(raw)
        if parsed is None:
            print("Не понял. Пример: 0 +")
            continue
        index, vote = parsed
        try:
            service.set_item_feedback(
                trip_id,
                section=section_key,
                item_index=index,
                vote=vote,
                program_data=program_data,
            )
        except ValueError as exc:
            print(f"Ошибка: {exc}")
            continue
        label = {1: "лайк", -1: "дизлайк", None: "снята оценка"}[vote]
        print(f"Сохранено: {label} на пункт [{index}]")


def run_feedback_session(
    service: TripService,
    trip_id: int,
    *,
    program_data: dict[str, Any] | None = None,
    scope: str = "full",
) -> None:
    """Интерактивная оценка пунктов до выхода пользователя."""
    section_options = [(key, _SECTION_TITLES[key]) for key in _CLI_VOTABLE_SECTIONS]
    while True:
        view = _load_view(service, trip_id, program_data=program_data, scope=scope)
        if view is None:
            print("Программа не найдена.")
            return
        print_votable_sections(view)
        print("\nСекция для оценки (Enter — готово):")
        for index, (_, title) in enumerate(section_options, start=1):
            print(f"  {index}. {title}")
        raw = input("Номер [Enter = выход]: ").strip()
        if not raw:
            print("Готово.")
            return
        try:
            choice = int(raw)
        except ValueError:
            print("Некорректный номер.")
            continue
        if not 1 <= choice <= len(section_options):
            print("Некорректный номер.")
            continue
        section_key = section_options[choice - 1][0]
        _vote_in_section(
            service,
            trip_id,
            section_key,
            program_data=program_data,
            scope=scope,
        )


def offer_feedback_before_review(
    service: TripService,
    trip_id: int,
    *,
    program_data: dict[str, Any],
    scope: str,
) -> None:
    """Перед утверждением: показать пункты и предложить оценить."""
    view = _load_view(service, trip_id, program_data=program_data, scope=scope)
    if view is None:
        return
    print_votable_sections(view)
    raw = _normalize_line(input("Оценить пункты перед утверждением? [да/Нет]: "))
    if raw not in _YES:
        return
    run_feedback_session(
        service,
        trip_id,
        program_data=program_data,
        scope=scope,
    )
