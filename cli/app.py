"""CLI: меню (новая / продолжить), опросник, SQLite, invoke графа."""

from __future__ import annotations

import json
import os
from typing import Any

from langchain_core.messages import HumanMessage
from pydantic import ValidationError

from agents.graph import app
from agents.print_program import print_final_program
from config.settings import ensure_env
from db import (
    PlannedTripSummary,
    create_trip,
    ensure_user_profile_from_trips,
    get_latest_itinerary,
    get_preferences,
    get_trip,
    get_user_profile,
    init_db,
    list_planned_trips,
    list_trips,
    save_itinerary_version,
    save_preferences,
    save_user_profile,
    update_trip_status,
)
from input_validation import sanitize_and_validate
from models.schemas import FinalProgram
from models.state import AgentState
from observability import invoke_config, langsmith_enabled
from onboarding import (
    TripPreferences,
    build_search_context,
    resolve_preferences_for_new_trip,
)
from planning import REBUILD_SCOPES, human_message_for_scope, required_tools_for_scope
from search.context import set_session


def _prompt_line(label: str, default: str = "") -> str:
    """Запрашивает строку в терминале; Enter — значение по умолчанию."""
    if default:
        raw = input(f"{label} [{default}]: ").strip()
        return raw if raw else default
    return input(f"{label}: ").strip()


def _run_graph(state: AgentState) -> AgentState:
    """Запускает мультиагентный граф и возвращает финальное состояние."""
    trip_id = int(state["trip_id"])
    print(f"\nЗапуск: {state['origin_city']} → {state['city']}, {state['dates']}")
    if langsmith_enabled():
        print("Трейсинг: LangSmith включён (LANGCHAIN_TRACING_V2)")
    print(
        "Агенты: researcher → executor → writer → critic → human_review "
        "(1–2 минуты)...\n"
    )
    run_state: AgentState = {
        **state,
        "retry_count": state.get("retry_count", 0),
        "approved": False,
        "critic_passed": False,
        "critic_notes": "",
    }
    config = invoke_config(
        trip_id,
        rebuild_scope=state.get("rebuild_scope", "full"),
    )
    return app.invoke(run_state, config=config)


def _apply_preferences_to_session(prefs: TripPreferences) -> str:
    """Сохраняет предпочтения в search/context для tools и промптов."""
    ctx = build_search_context(prefs)
    set_session(prefs, ctx)
    return ctx


def _collect_new_trip_inputs() -> tuple[str, str, str, str]:
    city_raw = _prompt_line("Город поездки")
    dates_raw = _prompt_line("Даты (например, 15-18 июля 2026)")
    origin_raw = _prompt_line("Город вылета", default="Москва")
    user_message_raw = _prompt_line(
        "Ваш запрос",
        default="Составь культурную программу поездки",
    )
    city = sanitize_and_validate(city_raw, "city")
    dates = sanitize_and_validate(dates_raw, "dates")
    origin_city = sanitize_and_validate(origin_raw, "city")
    user_message = sanitize_and_validate(user_message_raw, "message")
    return city, dates, origin_city, user_message


def _choose_rebuild_scope(*, has_program: bool) -> str:
    """Выбор полной или частичной пересборки программы."""
    if not has_program:
        print("\nСохранённой программы нет — будет полная сборка.")
        return "full"
    return _prompt_choice("Что пересобрать?", REBUILD_SCOPES, "full")


def _choose_trip_from_list() -> int | None:
    trips = list_trips()
    if not trips:
        print("Сохранённых поездок нет. Создайте новую.")
        return None
    print("\n--- Сохранённые поездки ---")
    for trip in trips:
        print(
            f"  [{trip.id}] {trip.city}, {trip.dates} "
            f"({trip.origin_city}) — {trip.status}"
        )
    raw = _prompt_line("ID поездки для продолжения")
    try:
        return int(raw)
    except ValueError:
        print("Некорректный ID.")
        return None


def _choose_planned_trip_from_list(
    trips: list[PlannedTripSummary],
) -> int | None:
    """Выбор поездки с программой по номеру в списке."""
    print("\n--- Запланированные поездки ---")
    for index, trip in enumerate(trips, start=1):
        print(
            f"  {index}. [{trip.id}] {trip.city}, {trip.dates} "
            f"({trip.origin_city}) — {trip.status}, "
            f"программа v{trip.last_version} ({trip.last_scope})"
        )
    raw = _prompt_line("Номер поездки")
    try:
        choice = int(raw)
    except ValueError:
        print("Некорректный номер.")
        return None
    if 1 <= choice <= len(trips):
        return trips[choice - 1].id
    print("Номер вне списка.")
    return None


def _resolve_details_trip_id() -> int | None:
    """
    Выбирает поездку для просмотра:
    одна запланированная — сразу; несколько незавершённых — список.
    """
    planned = list_planned_trips()
    if not planned:
        print("\nНет поездок с сохранённой программой.")
        return None

    if len(planned) == 1:
        return planned[0].id

    incomplete = [trip for trip in planned if trip.status != "approved"]
    if len(incomplete) == 1:
        return incomplete[0].id
    if len(incomplete) > 1:
        return _choose_planned_trip_from_list(incomplete)

    print("\nВсе поездки с программой отмечены как завершённые.")
    return _choose_planned_trip_from_list(planned)


def _print_trip_details(trip_id: int) -> None:
    """Печатает метаданные, предпочтения и последнюю программу из БД."""
    trip = get_trip(trip_id)
    if trip is None:
        print(f"Поездка #{trip_id} не найдена.")
        return

    print("\n" + "=" * 60)
    print(f"ПОЕЗДКА #{trip_id}")
    print("=" * 60)
    print(f"Маршрут: {trip['origin_city']} → {trip['city']}")
    print(f"Даты: {trip['dates']}")
    print(f"Статус: {trip['status']}")
    if trip.get("user_query"):
        print(f"Запрос: {trip['user_query']}")

    prefs_data = get_preferences(trip_id)
    if prefs_data:
        print("\n--- Предпочтения (опросник) ---")
        try:
            prefs = TripPreferences.model_validate(prefs_data)
            print(build_search_context(prefs))
        except ValidationError:
            print(json.dumps(prefs_data, ensure_ascii=False, indent=2))
    else:
        print("\n--- Предпочтения ---\nне сохранялись")

    latest = get_latest_itinerary(trip_id)
    if latest is None:
        print("\n--- Программа ---\nещё не сформирована")
        print("=" * 60)
        return

    print(
        f"\n--- Программа (версия {latest['version']}, "
        f"scope={latest['scope']}) ---"
    )
    program = FinalProgram.model_validate(latest["program"])
    print_final_program(program)


def _prompt_choice(label: str, options: list[tuple[str, str]], default_key: str) -> str:
    """Выбор пункта меню; Enter — значение по умолчанию."""
    print(f"\n{label}")
    default_index = next(
        (i for i, (key, _) in enumerate(options, start=1) if key == default_key),
        1,
    )
    for index, (_, text) in enumerate(options, start=1):
        mark = " (по умолчанию)" if index == default_index else ""
        print(f"  {index}. {text}{mark}")
    raw = input(f"Номер [Enter = {default_index}]: ").strip()
    if not raw:
        return default_key
    try:
        choice = int(raw)
    except ValueError:
        return default_key
    if 1 <= choice <= len(options):
        return options[choice - 1][0]
    return default_key


def main() -> None:
    ensure_env()

    init_db()
    ensure_user_profile_from_trips()
    search_backend = "Tavily" if os.getenv("TAVILY_API_KEY", "").strip() else "ddgs (ru-ru)"
    print("=" * 60)
    print("Туристический ассистент")
    print(f"Поиск данных: {search_backend}")
    print(f"База поездок: {os.getenv('DATABASE_PATH', 'data/trips.db')}")
    print("=" * 60)

    mode = _prompt_choice(
        "Режим",
        [
            ("new", "Новая поездка"),
            ("continue", "Продолжить сохранённую поездку"),
            ("details", "Показать подробности поездки"),
        ],
        "new",
    )

    if mode == "details":
        details_trip_id = _resolve_details_trip_id()
        if details_trip_id is not None:
            _print_trip_details(details_trip_id)
        raise SystemExit(0)

    trip_id: int
    city: str
    dates: str
    origin_city: str
    user_message: str
    search_context: str
    preferences_dict: dict[str, Any]
    rebuild_scope: str = "full"
    base_program: dict[str, Any] | None = None

    try:
        if mode == "continue":
            chosen = _choose_trip_from_list()
            if chosen is None:
                raise SystemExit(0)
            trip = get_trip(chosen)
            if trip is None:
                print(f"Поездка #{chosen} не найдена.")
                raise SystemExit(1)
            trip_id = int(trip["id"])
            city = trip["city"]
            dates = trip["dates"]
            origin_city = trip["origin_city"]
            user_message = trip.get("user_query") or "Обнови культурную программу поездки"
            prefs_data = get_preferences(trip_id)
            if prefs_data:
                prefs = TripPreferences.model_validate(prefs_data)
                search_context = _apply_preferences_to_session(prefs)
                preferences_dict = prefs.model_dump()
            else:
                search_context = ""
                preferences_dict = {}
                print("Предпочтения не найдены — поиск без опросника.")
            latest = get_latest_itinerary(trip_id)
            base_program = latest["program"] if latest else None
            if latest:
                print(
                    f"Последняя версия программы: v{latest['version']} "
                    f"({latest['scope']})"
                )
            rebuild_scope = _choose_rebuild_scope(has_program=base_program is not None)
            user_message = human_message_for_scope(rebuild_scope)
        else:
            city, dates, origin_city, user_message = _collect_new_trip_inputs()
            profile_data = get_user_profile()
            prefs = resolve_preferences_for_new_trip(
                has_profile=profile_data is not None,
                profile_data=profile_data,
            )
            preferences_dict = prefs.model_dump()
            search_context = _apply_preferences_to_session(prefs)
            save_user_profile(preferences_dict)
            trip_id = create_trip(city, dates, origin_city, user_message)
            save_preferences(trip_id, preferences_dict)
            print(f"Поездка сохранена в БД: id={trip_id}")

        update_trip_status(trip_id, "building")

        initial_state: AgentState = {
            "trip_id": trip_id,
            "city": city,
            "dates": dates,
            "origin_city": origin_city,
            "search_context": search_context,
            "preferences": preferences_dict,
            "rebuild_scope": rebuild_scope,
            "retry_count": 0,
            "approved": False,
            "critic_passed": False,
            "critic_notes": "",
            "messages": [HumanMessage(content=user_message)],
        }
        if base_program is not None:
            initial_state["base_program"] = base_program

        print(f"Режим пересборки: {rebuild_scope}")
        if rebuild_scope != "full":
            tools = required_tools_for_scope(rebuild_scope)
            if tools:
                print(f"  → веб-поиск: {', '.join(tools)}")
            else:
                print("  → без веб-поиска")

        final_state = _run_graph(initial_state)
        program = final_state.get("program")
        if program:
            version_id = save_itinerary_version(
                trip_id,
                program,
                scope=rebuild_scope,
                approved=bool(final_state.get("approved")),
            )
            print(f"\nПрограмма сохранена: trip_id={trip_id}, version_id={version_id}")
        else:
            print("\nПредупреждение: программа не попала в состояние графа.")

    except ValueError as exc:
        print(f"Ошибка валидации входа: {exc}")
        raise SystemExit(1) from exc
    except SystemExit:
        raise
    except Exception as exc:
        print(f"Ошибка выполнения: {exc}")
        raise SystemExit(1) from exc
