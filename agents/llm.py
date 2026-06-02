"""LLM через ProxyAPI: planner с tool_calls, finalize со structured output.

Поддерживает роутинг модели по направлению (Россия vs зарубежье), чтобы:
- для поездок по РФ использовать одну модель/endpoint,
- для зарубежных поездок — другую,
при этом оставаясь совместимыми с текущим OpenAI-compatible API.
"""

from __future__ import annotations

import os
from functools import lru_cache

from langchain_openai import ChatOpenAI

from config import settings
from models.schemas import FinalProgram
from search.tools import TOOLS

_RUS_CITIES_LATIN = {
    "moscow",
    "saint petersburg",
    "st petersburg",
    "st. petersburg",
    "st-petersburg",
    "petersburg",
    "kazan",
    "sochi",
    "novosibirsk",
    "yekaterinburg",
    "ekaterinburg",
    "nizhny novgorod",
    "vladivostok",
    "kaliningrad",
}

_FOREIGN_HINTS_CYR = (
    "франц",
    "итал",
    "испан",
    "герман",
    "англи",
    "сша",
    "оаэ",
    "турц",
    "греци",
    "кипр",
    "япони",
    "китай",
    "тайланд",
    "вьетнам",
    "грузия",
    "армени",
    "казахстан",
)


def _has_cyrillic(text: str) -> bool:
    return any("А" <= ch <= "я" or ch in ("ё", "Ё") for ch in text)


def infer_llm_region(city: str) -> str:
    """
    Грубая эвристика: определяем, РФ это или зарубежье.
    Правила (по убыванию приоритета):
    - явные слова "россия"/"рф" → ru
    - явные намёки на иностранные страны (кириллица) → intl
    - кириллица в названии города → ru (частый кейс для РФ)
    - известные РФ-города латиницей → ru
    - иначе → intl
    """
    raw = (city or "").strip()
    low = raw.lower()
    if "россия" in low or " рф" in low or low.endswith("рф"):
        return "ru"
    if _has_cyrillic(low) and any(hint in low for hint in _FOREIGN_HINTS_CYR):
        return "intl"
    if _has_cyrillic(raw):
        return "ru"
    normalized = (
        low.replace(",", " ")
        .replace(".", " ")
        .replace("-", " ")
        .replace("  ", " ")
        .strip()
    )
    if normalized in _RUS_CITIES_LATIN:
        return "ru"
    return "intl"


def _env_llm_region_default() -> str:
    return os.getenv("LLM_REGION", settings.LLM_REGION).strip().lower() or "auto"


def _pick_model_and_base_url(*, region: str) -> tuple[str, str]:
    if region == "ru":
        model = os.getenv("LLM_MODEL_RU", settings.LLM_MODEL_RU)
        base_url = os.getenv("PROXY_BASE_URL_RU", os.getenv("PROXY_BASE_URL", settings.DEFAULT_PROXY_BASE_URL))
        return model, base_url
    if region == "intl":
        model = os.getenv("LLM_MODEL_INTL", settings.LLM_MODEL_INTL)
        base_url = os.getenv("PROXY_BASE_URL_INTL", os.getenv("PROXY_BASE_URL", settings.DEFAULT_PROXY_BASE_URL))
        return model, base_url
    # fallback
    return settings.LLM_MODEL, os.getenv("PROXY_BASE_URL", settings.DEFAULT_PROXY_BASE_URL)


def _extract_yandex_folder_id(model: str) -> str | None:
    """Извлекает folder_id из URI вида gpt://<folder_id>/<model>."""
    if not model.startswith("gpt://"):
        return None
    rest = model.removeprefix("gpt://")
    folder, _, _model = rest.partition("/")
    return folder or None


def _pick_api_key(*, region: str) -> str | None:
    """RU: Yandex Cloud; INTL: ProxyAPI / OpenAI."""
    if region == "ru":
        return (
            os.getenv("YANDEX_API_KEY")
            or os.getenv("YC_API_KEY")
            or os.getenv("OPENAI_API_KEY")
        )
    return os.getenv("OPENAI_API_KEY")


def _yandex_default_headers(*, model: str, base_url: str) -> dict[str, str] | None:
    if "llm.api.cloud.yandex.net" not in base_url:
        return None
    folder_id = os.getenv("YANDEX_FOLDER_ID") or _extract_yandex_folder_id(model)
    if not folder_id:
        return None
    return {"x-folder-id": folder_id}


@lru_cache(maxsize=4)
def _get_llm_cached(*, region: str) -> ChatOpenAI:
    model, base_url = _pick_model_and_base_url(region=region)
    api_key = _pick_api_key(region=region)
    extra: dict[str, object] = {}
    headers = _yandex_default_headers(model=model, base_url=base_url)
    if headers:
        extra["default_headers"] = headers
    return ChatOpenAI(
        model=model,
        temperature=settings.LLM_TEMPERATURE,
        api_key=api_key,
        base_url=base_url,
        **extra,
    )


def get_llm(*, city: str = "", llm_region: str | None = None) -> ChatOpenAI:
    """
    Возвращает LLM под поездку.
    - llm_region: "ru"/"intl"/"auto"/None
    - если "auto"/None — берём env `LLM_REGION`, и если он auto — эвристику по городу
    """
    region = (llm_region or "").strip().lower() or "auto"
    if region == "auto":
        env_region = _env_llm_region_default()
        region = infer_llm_region(city) if env_region == "auto" else env_region
    if region not in ("ru", "intl"):
        region = "intl"
    return _get_llm_cached(region=region)


def get_llm_with_tools(*, city: str = "", llm_region: str | None = None):
    return get_llm(city=city, llm_region=llm_region).bind_tools(TOOLS)


def get_llm_final(*, city: str = "", llm_region: str | None = None):
    return get_llm(city=city, llm_region=llm_region).with_structured_output(
        FinalProgram,
        method="json_schema",
    )

__all__ = [
    "infer_llm_region",
    "get_llm",
    "get_llm_final",
    "get_llm_with_tools",
]
