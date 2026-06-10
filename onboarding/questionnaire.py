"""Интерактивный опросник: состав группы (+ legacy defaults в TripPreferences)."""

from __future__ import annotations

from onboarding.preferences import (
    TripPreferences,
    build_search_context,
    normalize_trip_preferences,
)


def _prompt_choice(
    label: str,
    options: list[tuple[str, str]],
    default_key: str,
) -> str:
    """Выбор из нумерованного списка; Enter — default."""
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


def _prompt_yes_no(label: str, *, default: bool = True) -> bool:
    """y/n; Enter — значение по умолчанию."""
    hint = "Y/n" if default else "y/N"
    raw = input(f"{label} [{hint}]: ").strip().lower()
    if not raw:
        return default
    return raw in {"y", "yes", "д", "да"}


def _print_preferences_summary(prefs: TripPreferences) -> None:
    print("\n--- Сохранённые предпочтения ---")
    print(build_search_context(prefs))
    print("---\n")


def run_questionnaire(*, defaults: TripPreferences | None = None) -> TripPreferences:
    """
    Опросник: состав группы.
    Темп (packed) и передвижение (mixed) заданы в коде.
    """
    if defaults is None:
        print("\n--- Опросник ---")
        print("Темп — насыщенный, передвижение — метро + пешком (фиксировано).\n")
    else:
        print("\n--- Уточняющий опрос ---")
        print("Enter — оставить текущее значение в квадратных скобках.\n")

    base = normalize_trip_preferences(defaults) if defaults else None
    party_default = base.travel_party if base else "couple"

    party = _prompt_choice(
        "С кем едете? (число пассажиров в ссылках на билеты)",
        [
            ("solo", "1 взрослый"),
            ("couple", "2 взрослых"),
            ("parent_child", "1 взрослый + 1 ребёнок"),
            ("family", "2 взрослых + 1 ребёнок"),
            ("family_two", "2 взрослых + 2 ребёнка"),
            ("friends", "3 взрослых"),
        ],
        party_default,
    )

    prefs = normalize_trip_preferences({"travel_party": party})
    print("\n✓ Предпочтения учтены.\n")
    return prefs


def run_clarifying_questionnaire(base: TripPreferences) -> TripPreferences:
    """Уточняющий опрос с дефолтом из профиля."""
    return run_questionnaire(defaults=base)


def resolve_preferences_for_new_trip(
    *,
    has_profile: bool,
    profile_data: dict | None,
) -> TripPreferences:
    """
    Первый запуск — опросник (состав группы).
    Повторный — сохранённые prefs; заново — по явному согласию.
    """
    if not has_profile or profile_data is None:
        return run_questionnaire()

    saved = normalize_trip_preferences(profile_data)
    _print_preferences_summary(saved)

    if _prompt_yes_no("Пройти опрос предпочтений заново?", default=False):
        return run_questionnaire(defaults=saved)

    print("Используем сохранённые предпочтения (опросник пропущен).\n")
    return saved
