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
    "landmarks": {
        "include_any": (
            "достопримечатель",
            "что посмотреть",
            "главные мест",
            "пешая прогул",
            "музей",
            "музеи",
            "парк",
            "площад",
            "набереж",
            "кремл",
            "собор",
            "храм",
            "памятник",
            "сквер",
            "усадьб",
            "монаст",
            "театр",
            "галере",
            "маршрут по городу",
        ),
        "exclude_any": (
            "aviasales",
            "rzd.ru",
            "tutu.ru",
            "отель",
            "гостиниц",
            "бронирован",
            "авиабилет",
            "жд билет",
            "kinopoisk",
            "ресторан",
            "кафе",
            "2gis.ru/restaurant",
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

DEFAULT_LLM_BASE_URL = "https://openrouter.ai/api/v1"
# gpt-4.1-mini на Azure поддерживает tools + structured_outputs (gpt-4o-mini — только OpenAI).
LLM_MODEL = "openai/gpt-4.1-mini"
LLM_TEMPERATURE = 0.2

# Белый список OpenRouter (only + order). DeepInfra не хостит openai/* на OpenRouter.
DEFAULT_OPENROUTER_PROVIDERS: tuple[str, ...] = ("Azure",)

# Альтернативы дефолту: (slug, провайдеры OpenRouter). См. README «Модели LLM».
RECOMMENDED_ALTERNATIVE_LLM_MODELS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("openai/gpt-4o-mini", ("OpenAI",)),
    ("google/gemini-2.5-flash-lite", ("Google", "Google AI Studio")),
    ("deepseek/deepseek-chat-v3.1", ("DeepInfra",)),
    ("meta-llama/llama-3.3-70b-instruct", ("DeepInfra", "Together")),
    ("mistralai/mistral-nemo", ("Mistral",)),
)


def get_llm_api_key() -> str:
    """Ключ OpenRouter (или другого OpenAI-compatible провайдера)."""
    return os.getenv("LLM_API_KEY", "").strip()


def get_llm_base_url() -> str:
    """Base URL OpenAI-compatible API; по умолчанию OpenRouter."""
    explicit = os.getenv("LLM_BASE_URL", "").strip()
    if explicit:
        return explicit
    legacy = os.getenv("PROXY_BASE_URL", "").strip()
    if legacy:
        return legacy
    return DEFAULT_LLM_BASE_URL


def _split_csv_env(name: str) -> list[str]:
    return [part.strip() for part in os.getenv(name, "").split(",") if part.strip()]


def get_openrouter_providers() -> list[str]:
    """
    Белый список провайдеров OpenRouter (порядок = приоритет).
    LLM_OPENROUTER_PROVIDERS не задан — DEFAULT_OPENROUTER_PROVIDERS;
    пустая строка — без ограничений (любой провайдер OpenRouter).
    """
    raw = os.getenv("LLM_OPENROUTER_PROVIDERS")
    if raw is not None:
        return _split_csv_env("LLM_OPENROUTER_PROVIDERS")
    legacy = os.getenv("LLM_OPENROUTER_PROVIDER_ORDER")
    if legacy is not None:
        return _split_csv_env("LLM_OPENROUTER_PROVIDER_ORDER")
    return list(DEFAULT_OPENROUTER_PROVIDERS)


def get_llm_extra_body() -> dict[str, object] | None:
    """OpenRouter: only/order + require_parameters (нужны tools и structured output)."""
    if "openrouter.ai" not in get_llm_base_url():
        return None

    providers = get_openrouter_providers()
    if not providers:
        return {"provider": {"allow_fallbacks": True, "require_parameters": True}}
    return {
        "provider": {
            "only": providers,
            "order": providers,
            "allow_fallbacks": False,
            "require_parameters": True,
        }
    }


def is_placeholder_secret(value: str) -> bool:
    """Плейсхолдер из .env.example, а не реальный ключ/токен."""
    raw = (value or "").strip()
    if not raw:
        return True
    lowered = raw.lower()
    if lowered in ("sk-...", "sk-or-...", "sk-your-key", "changeme", "your-api-key"):
        return True
    return "..." in raw or ("<" in raw and ">" in raw)


def ensure_env() -> None:
    """Проверяет обязательные переменные окружения перед запуском CLI."""
    api_key = get_llm_api_key()
    if not api_key:
        raise SystemExit(
            "Ошибка: не задан LLM_API_KEY. "
            "Создайте файл .env (см. .env.example): LLM_API_KEY=sk-or-..."
        )
    if is_placeholder_secret(api_key):
        raise SystemExit(
            "Ошибка: LLM_API_KEY в .env — плейсхолдер из .env.example (sk-or-...), "
            "а не реальный ключ.\n"
            "Вставьте ключ с https://openrouter.ai/keys.\n"
            "Если ключ был раньше — восстановите из бэкапа или сгенерируйте новый."
        )
