"""CLI: меню (новая / продолжить), опросник, SQLite, invoke графа."""

from __future__ import annotations

import json
import os

from pydantic import ValidationError

from agents.print_program import print_final_program
from config.settings import ensure_env
from db import (
    PlannedTripSummary,
    ensure_user_profile_from_trips,
    get_trip,
    get_user_profile,
    init_db,
    list_planned_trips,
    list_trips,
    update_trip_status,
)
from models.state import AgentState
from observability import langfuse_enabled, langsmith_enabled
from onboarding import (
    TripPreferences,
    build_search_context,
    resolve_preferences_for_new_trip,
)
from planning import REBUILD_SCOPES, required_tools_for_scope
from cli.feedback import run_feedback_session
from services import TripService
from services.errors import format_runtime_error

DEFAULT_USER_QUERY = "Составь культурную программу поездки"


def _prompt_line(label: str, default: str = "") -> str:
    """Запрашивает строку в терминале; Enter — значение по умолчанию."""
    if default:
        raw = input(f"{label} [{default}]: ").strip()
        return raw if raw else default
    return input(f"{label}: ").strip()


def _collect_new_trip_inputs() -> tuple[str, str, str, str]:
    city_raw = _prompt_line("Город поездки")
    dates_raw = _prompt_line("Даты (например, 15-18 июля 2026)")
    origin_raw = _prompt_line("Город вылета", default="Москва")
    return city_raw, dates_raw, origin_raw, DEFAULT_USER_QUERY


def _choose_rebuild_scope(*, has_program: bool) -> str:
    """Выбор полной или частичной пересборки программы."""
    if not has_program:
        print("\nСохранённой программы нет — будет полная сборка.")
        return "full"
    return _prompt_choice("Что пересобрать?", REBUILD_SCOPES, "full")


def _confirm_delete_trip(trip_id: int, *, city: str, dates: str) -> bool:
    """Подтверждение удаления поездки (номер пункта — без путаницы раскладок)."""
    print(f"\nУдалить поездку #{trip_id}: {city}, {dates}?")
    choice = _prompt_choice(
        "Подтвердить удаление?",
        [
            ("yes", "Да, удалить"),
            ("no", "Нет, отменить"),
        ],
        "no",
    )
    return choice == "yes"


def _feedback_trip_flow(service: TripService) -> None:
    """Оценка пунктов сохранённой программы."""
    chosen = _choose_trip_from_list(prompt="ID поездки для оценки")
    if chosen is None:
        return
    if service.get_program_view(chosen) is None:
        print("У поездки нет сохранённой программы.")
        return
    run_feedback_session(service, chosen)


def _delete_trip_flow(service: TripService) -> None:
    """Выбор поездки из списка и удаление из БД."""
    chosen = _choose_trip_from_list(prompt="ID поездки для удаления")
    if chosen is None:
        return
    trip = get_trip(chosen)
    if trip is None:
        print(f"Поездка #{chosen} не найдена.")
        return
    if not _confirm_delete_trip(
        chosen,
        city=trip["city"],
        dates=trip["dates"],
    ):
        print("Удаление отменено.")
        return
    try:
        service.delete_trip_by_id(chosen)
    except ValueError as exc:
        print(f"Ошибка: {exc}")
        raise SystemExit(1) from exc
    print(f"Поездка #{chosen} удалена.")


def _choose_trip_from_list(*, prompt: str = "ID поездки для продолжения") -> int | None:
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
    raw = _prompt_line(prompt)
    try:
        return int(raw)
    except ValueError:
        print("Некорректный ID.")
        return None


def _choose_planned_trip_from_list(
    trips: list[PlannedTripSummary],
    *,
    prompt: str = "Номер поездки",
) -> int | None:
    """Выбор поездки с программой по номеру в списке."""
    print("\n--- Поездки с сохранённой программой ---")
    for index, trip in enumerate(trips, start=1):
        print(
            f"  {index}. [{trip.id}] {trip.city}, {trip.dates} "
            f"({trip.origin_city}) — {trip.status}, "
            f"программа v{trip.last_version} ({trip.last_scope})"
        )
    raw = _prompt_line(prompt)
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
    """Выбор поездки для просмотра — всегда из списка с программой."""
    planned = list_planned_trips()
    if not planned:
        print("\nНет поездок с сохранённой программой.")
        return None
    return _choose_planned_trip_from_list(
        planned,
        prompt="Номер поездки для просмотра",
    )


def _print_trip_details(service: TripService, trip_id: int) -> None:
    """Печатает метаданные, предпочтения и последнюю программу из БД."""
    details = service.get_trip_details(trip_id)
    if details is None:
        print(f"Поездка #{trip_id} не найдена.")
        return

    trip = details.trip
    print("\n" + "=" * 60)
    print(f"ПОЕЗДКА #{trip_id}")
    print("=" * 60)
    print(f"Маршрут: {trip['origin_city']} → {trip['city']}")
    print(f"Даты: {trip['dates']}")
    print(f"Статус: {trip['status']}")
    if trip.get("user_query"):
        print(f"Запрос: {trip['user_query']}")

    if details.preferences:
        print("\n--- Предпочтения (опросник) ---")
        try:
            prefs = TripPreferences.model_validate(details.preferences)
            print(build_search_context(prefs))
        except ValidationError:
            print(json.dumps(details.preferences, ensure_ascii=False, indent=2))
    else:
        print("\n--- Предпочтения ---\nне сохранялись")

    latest = details.latest_itinerary
    if latest is None:
        print("\n--- Программа ---\nещё не сформирована")
        print("=" * 60)
        return

    print(
        f"\n--- Программа (версия {latest['version']}, "
        f"scope={latest['scope']}) ---"
    )
    program = service.parse_program(latest["program"])
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


def _print_run_progress(message: str) -> None:
    if "Запуск:" in message:
        print(f"\n{message}")
        if langsmith_enabled():
            print("Трейсинг: LangSmith включён (LANGCHAIN_TRACING_V2)")
        if langfuse_enabled():
            print("Трейсинг: LangFuse включён (LANGFUSE_ENABLED)")
        print(
            "Агенты: researcher → executor → writer → critic → human_review "
            "(1–2 минуты)...\n"
        )


def main() -> None:
    ensure_env()
    service = TripService()

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
            ("feedback", "Оценить пункты поездки"),
            ("delete", "Удалить поездку"),
        ],
        "new",
    )

    if mode == "feedback":
        _feedback_trip_flow(service)
        raise SystemExit(0)

    if mode == "delete":
        _delete_trip_flow(service)
        raise SystemExit(0)

    if mode == "details":
        details_trip_id = _resolve_details_trip_id()
        if details_trip_id is not None:
            _print_trip_details(service, details_trip_id)
        raise SystemExit(0)

    trip_id: int
    initial_state: AgentState
    rebuild_scope: str = "full"

    try:
        if mode == "continue":
            chosen = _choose_trip_from_list()
            if chosen is None:
                raise SystemExit(0)
            details = service.get_trip_details(chosen)
            if details is None:
                print(f"Поездка #{chosen} не найдена.")
                raise SystemExit(1)
            trip_id = chosen
            has_program = details.latest_itinerary is not None
            if details.latest_itinerary:
                latest = details.latest_itinerary
                print(
                    f"Последняя версия программы: v{latest['version']} "
                    f"({latest['scope']})"
                )
            rebuild_scope = _choose_rebuild_scope(has_program=has_program)
            if not details.preferences:
                print("Предпочтения не найдены — поиск без опросника.")
            initial_state = service.prepare_continue_trip(trip_id, rebuild_scope)
        else:
            city_raw, dates_raw, origin_raw, user_message_raw = _collect_new_trip_inputs()
            profile_data = get_user_profile()
            prefs = resolve_preferences_for_new_trip(
                has_profile=profile_data is not None,
                profile_data=profile_data,
            )
            trip_id = service.create_new_trip(
                city=city_raw,
                dates=dates_raw,
                origin_city=origin_raw,
                user_query=user_message_raw,
                preferences=prefs,
            )
            print(f"Поездка сохранена в БД: id={trip_id}")
            trip = get_trip(trip_id)
            assert trip is not None
            initial_state = service.build_initial_state(
                trip_id=trip_id,
                city=trip["city"],
                dates=trip["dates"],
                origin_city=trip["origin_city"],
                search_context=build_search_context(prefs),
                preferences_dict=prefs.model_dump(),
                rebuild_scope="full",
                user_message=trip.get("user_query") or user_message_raw,
                review_mode="cli",
            )
            rebuild_scope = "full"

        update_trip_status(trip_id, "building")

        print(f"Режим пересборки: {rebuild_scope}")
        if rebuild_scope != "full":
            tools = required_tools_for_scope(rebuild_scope)
            if tools:
                print(f"  → веб-поиск: {', '.join(tools)}")
            else:
                print("  → без веб-поиска")

        result = service.run_graph(
            initial_state,
            review_mode="cli",
            on_progress=_print_run_progress,
        )
        if result.version_id is not None:
            print(f"\nПрограмма сохранена: trip_id={trip_id}, version_id={result.version_id}")
        else:
            print("\nПредупреждение: программа не попала в состояние графа.")

    except ValueError as exc:
        print(f"Ошибка валидации входа: {exc}")
        raise SystemExit(1) from exc
    except SystemExit:
        raise
    except Exception as exc:
        print(format_runtime_error(exc))
        raise SystemExit(1) from exc
