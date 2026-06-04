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
AVIA_API_TIMEOUT = 30
AVIA_API_LIMIT = 5
MAX_SEARCH_RESULTS = 10
KIND_MAX_RESULTS: dict[str, int] = {
    "tickets": 12,
    "events": 12,
    "restaurants": 18,
    "dining": 14,
}
DIGEST_LIMITS: dict[str, int] = {
    "tickets": 25,
    "events": 8,
    "restaurants": 20,
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
    "dining": {
        "include_any": (
            "ресторан",
            "кафе",
            "2gis",
            "tripadvisor",
            "яндекс.карт",
            "где поесть",
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

# Роутинг моделей (Россия vs зарубежье)
# - LLM_REGION: auto|ru|intl — принудительный выбор региона (по умолчанию auto)
# - LLM_MODEL_RU / LLM_MODEL_INTL: имена моделей для регионов (если не заданы — LLM_MODEL)
# - PROXY_BASE_URL_RU / PROXY_BASE_URL_INTL: endpoint'ы (если не заданы — PROXY_BASE_URL/DEFAULT_PROXY_BASE_URL)
LLM_REGION = "auto"
LLM_MODEL_RU = LLM_MODEL
LLM_MODEL_INTL = LLM_MODEL


def is_placeholder_secret(value: str) -> bool:
    """Плейсхолдер из .env.example, а не реальный ключ/токен."""
    raw = (value or "").strip()
    if not raw:
        return True
    lowered = raw.lower()
    if lowered in ("sk-...", "sk-your-key", "changeme", "your-api-key"):
        return True
    return "..." in raw or ("<" in raw and ">" in raw)


def ensure_env() -> None:
    """Проверяет обязательные переменные окружения перед запуском CLI."""
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise SystemExit(
            "Ошибка: не задан OPENAI_API_KEY. "
            "Создайте файл .env (см. .env.example): OPENAI_API_KEY=sk-..."
        )
    if is_placeholder_secret(api_key):
        raise SystemExit(
            "Ошибка: OPENAI_API_KEY в .env — плейсхолдер из .env.example (sk-...), "
            "а не ключ ProxyAPI.\n"
            "Вставьте ключ с https://proxyapi.ru → личный кабинет → API keys.\n"
            "Если ключ был раньше — восстановите из бэкапа или сгенерируйте новый."
        )
