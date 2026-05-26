"""Интерактивный опросник: полный (первый раз) и уточняющий (с дефолтами)."""

from __future__ import annotations

from onboarding.preferences import TripPreferences, build_search_context


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


def _prompt_line(label: str, default: str = "") -> str:
    if default:
        raw = input(f"{label} [{default}]: ").strip()
        return raw if raw else default
    return input(f"{label}: ").strip()


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
    Полный опросник (7 вопросов).
    Если передан defaults — Enter оставляет прежние ответы (уточняющий режим).
    """
    if defaults is None:
        print("\n--- Опросник (7 вопросов) ---")
        print("Ответы улучшат поиск билетов, афиши и ресторанов.\n")
    else:
        print("\n--- Уточняющий опрос ---")
        print("Enter — оставить текущее значение в квадратных скобках.\n")

    base = defaults
    pace_default = base.pace if base else "moderate"
    budget_default = base.budget if base else "medium"
    interests_default = ", ".join(base.interests) if base and base.interests else "музеи, архитектура, выставки"
    cuisine_default = base.cuisine if base and base.cuisine else "любая местная"
    rating_default = str(base.min_restaurant_rating) if base else "4.5"
    transport_default = base.transport_preference if base else "mixed"
    party_default = base.travel_party if base else "couple"
    special_default = base.special_notes if base and base.special_notes else ""

    pace = _prompt_choice(
        "1. Темп поездки?",
        [
            ("relaxed", "Спокойно — 1–2 объекта в день"),
            ("moderate", "Умеренно — 2–3 объекта"),
            ("packed", "Насыщенно — максимум впечатлений"),
        ],
        pace_default,
    )

    budget = _prompt_choice(
        "2. Бюджет?",
        [
            ("economy", "Эконом"),
            ("medium", "Средний"),
            ("unlimited", "Без жёстких ограничений"),
        ],
        budget_default,
    )

    interests_raw = _prompt_line("3. Интересы через запятую", default=interests_default)
    interests = [part.strip() for part in interests_raw.split(",") if part.strip()]

    cuisine = _prompt_line("4. Предпочтения по кухне", default=cuisine_default)

    rating_raw = _prompt_line("5. Минимальный рейтинг ресторанов (1–5)", default=rating_default)
    try:
        min_rating = float(rating_raw.replace(",", "."))
    except ValueError:
        min_rating = float(rating_default.replace(",", ".")) if rating_default else 4.5
    min_rating = max(1.0, min(5.0, min_rating))

    transport = _prompt_choice(
        "6. Передвижение по городу?",
        [
            ("metro", "Метро и общественный транспорт"),
            ("walking", "В основном пешком"),
            ("taxi", "Такси"),
            ("mixed", "Метро + пешком"),
        ],
        transport_default,
    )

    party = _prompt_choice(
        "7. С кем едете?",
        [
            ("solo", "Один/одна"),
            ("couple", "Пара"),
            ("family", "С детьми"),
            ("friends", "Компания друзей"),
        ],
        party_default,
    )

    special = _prompt_line("Доп. пожелания для этой поездки (Enter — пропустить)", default=special_default)

    prefs = TripPreferences(
        pace=pace,
        budget=budget,
        interests=interests,
        cuisine=cuisine,
        min_restaurant_rating=min_rating,
        transport_preference=transport,
        travel_party=party,
        special_notes=special,
    )
    print("\n✓ Предпочтения учтены.\n")
    return prefs


def run_clarifying_questionnaire(base: TripPreferences) -> TripPreferences:
    """Уточняющий опрос: те же 7 вопросов с дефолтами из профиля."""
    return run_questionnaire(defaults=base)


def resolve_preferences_for_new_trip(
    *,
    has_profile: bool,
    profile_data: dict | None,
) -> TripPreferences:
    """
    Первый запуск — полный опросник (7 вопросов).
    Если опросник уже проходили — сохранённые prefs без вопросов;
    заново — только по явному согласию.
    """
    if not has_profile or profile_data is None:
        return run_questionnaire()

    saved = TripPreferences.model_validate(profile_data)
    _print_preferences_summary(saved)

    if _prompt_yes_no("Пройти опрос предпочтений заново?", default=False):
        return run_questionnaire(defaults=saved)

    print("Используем сохранённые предпочтения (опросник пропущен).\n")
    return saved
