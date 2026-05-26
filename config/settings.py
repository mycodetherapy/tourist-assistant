"""Конфигурация из .env и константы поиска/LLM."""

from __future__ import annotations

import os
import re

from dotenv import load_dotenv

load_dotenv()

# Политика ввода из терминала
MAX_LENGTHS: dict[str, int] = {
    "city": 500,
    "dates": 500,
    "message": 2000,
}

INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"ignore\s+(all\s+)?(previous|prior)\s+instructions",
        r"disregard\s+(all\s+)?(previous|prior)",
        r"system\s*:",
        r"assistant\s*:",
        r"<\|",
        r"\{\{",
        r"```",
        r"jailbreak",
        r"you\s+are\s+now",
        r"новые\s+инструкции",
        r"забудь\s+(все|предыдущ)",
        r"игнорируй\s+(все|предыдущ)",
    )
]

# Веб-поиск
SEARCH_TIMEOUT = 30
MAX_SEARCH_RESULTS = 10
KIND_MAX_RESULTS: dict[str, int] = {
    "tickets": 12,
    "events": 12,
    "restaurants": 18,
    "transport": 8,
    "dining": 14,
}
DIGEST_LIMITS: dict[str, int] = {
    "tickets": 25,
    "events": 15,
    "restaurants": 20,
    "transport": 10,
}
DDG_REGION = "ru-ru"

SEARCH_FILTERS: dict[str, dict[str, tuple[str, ...]]] = {
    "tickets": {
        "include_any": (
            "авиа",
            "рейс",
            "aviasales",
            "travel.yandex",
            "путешеств",
            "самолёт",
            "самолет",
            "аэрофлот",
            "победа",
            "rzd",
            "ржд",
            "жд билет",
            "tutu.ru",
            "tutu",
            "поезд",
            "плацкарт",
            "купе",
            "автобус",
            "bus.ru",
            "avibus",
            "blablacar",
            "flixbus",
            "eurobus",
        ),
        "exclude_any": (
            "музей",
            "эрмитаж",
            "фаберже",
            "афиша",
            "ресторан",
            "выставк",
            "концерт",
            "театр",
            "tripadvisor",
            "kinopoisk",
            "кинопоиск",
        ),
    },
    "events": {
        "include_any": (
            "музей",
            "выставк",
            "афиша",
            "концерт",
            "театр",
            "kassir",
            "эрмитаж",
            "филармон",
            "галере",
            "билет в музей",
        ),
        "exclude_any": (
            "aviasales",
            "travel.yandex",
            "ресторан",
            "tripadvisor",
            "2gis.ru/restaurant",
            "kinopoisk",
        ),
    },
    "restaurants": {
        "include_any": (
            "ресторан",
            "кафе",
            "2gis",
            "tripadvisor",
            "yandex.ru/maps",
            "яндекс.карт",
            "где поесть",
            "заведен",
            "кухн",
            "меню",
        ),
        "exclude_any": (
            "aviasales",
            "rzd.ru",
            "kinopoisk",
            "кинопоиск",
            "музей",
            "афиша",
            "метро схем",
        ),
    },
    "transport": {
        "include_any": (
            "метро",
            "транспорт",
            "маршрут",
            "яндекс.карт",
            "общественный",
            "проезд",
            "карта метро",
            "2gis",
        ),
        "exclude_any": (
            "aviasales",
            "ресторан",
            "tripadvisor",
            "kinopoisk",
        ),
    },
    "dining": {
        "include_any": (
            "ресторан",
            "кафе",
            "2gis",
            "tripadvisor",
            "метро",
            "транспорт",
            "маршрут",
            "яндекс.карт",
            "общественный",
        ),
        "exclude_any": (
            "aviasales",
            "kinopoisk",
            "кинопоиск",
            "афиша концерт",
        ),
    },
}

DEFAULT_PROXY_BASE_URL = "https://openai.api.proxyapi.ru/v1"
LLM_MODEL = "gpt-4o-mini"
LLM_TEMPERATURE = 0.2


def ensure_env() -> None:
    """Проверяет обязательные переменные окружения перед запуском CLI."""
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit(
            "Ошибка: не задан OPENAI_API_KEY. "
            "Создайте файл .env (см. .env.example): OPENAI_API_KEY=..."
        )
