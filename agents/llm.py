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
from config.settings import is_placeholder_secret
from models.schemas import ProgramDraft
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


def _is_yandex_base_url(base_url: str) -> bool:
    return "llm.api.cloud.yandex.net" in base_url


def _is_placeholder_folder_id(folder_id: str) -> bool:
    raw = (folder_id or "").strip()
    if not raw:
        return True
    lowered = raw.lower()
    if lowered in ("<folder_id>", "folder_id", "your_folder_id"):
        return True
    return "<" in raw or ">" in raw


def _extract_yandex_folder_id(model: str) -> str | None:
    """Извлекает folder_id из URI вида gpt://<folder_id>/<model>."""
    if not model.startswith("gpt://"):
        return None
    rest = model.removeprefix("gpt://")
    folder, _, _model = rest.partition("/")
    return folder or None


def _llm_config_issues(*, region: str) -> list[str]:
    """Проверяет, что endpoint и model согласованы (до HTTP-запроса к API)."""
    model, base_url = _pick_model_and_base_url(region=region)
    issues: list[str] = []

    if _is_yandex_base_url(base_url):
        if not model.startswith("gpt://"):
            issues.append(
                "для PROXY_BASE_URL_RU (Yandex) задайте LLM_MODEL_RU вида "
                "gpt://<folder_id>/aliceai-llm/latest"
            )
            return issues
        folder_id = os.getenv("YANDEX_FOLDER_ID") or _extract_yandex_folder_id(model)
        if _is_placeholder_folder_id(folder_id or ""):
            issues.append(
                "не задан каталог Yandex Cloud: замените <folder_id> в LLM_MODEL_RU "
                "или укажите YANDEX_FOLDER_ID в .env"
            )
        if not _pick_api_key(region="ru"):
            issues.append("для поездок по РФ нужен YANDEX_API_KEY (или YC_API_KEY)")
        return issues

    if model.startswith("gpt://"):
        issues.append(
            "LLM_MODEL_RU в формате gpt://... используйте только с "
            "PROXY_BASE_URL_RU=https://llm.api.cloud.yandex.net/v1; "
            "для ProxyAPI укажите LLM_MODEL_RU=gpt-4o-mini"
        )
    return issues


def _can_fallback_ru_to_intl() -> bool:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    return bool(key) and not is_placeholder_secret(key)


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
    if not _is_yandex_base_url(base_url):
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

    issues = _llm_config_issues(region=region)
    if issues:
        if region == "ru" and _can_fallback_ru_to_intl():
            print(
                "\nПредупреждение: конфигурация LLM для РФ (Yandex) неполная — "
                "используем зарубежную модель через ProxyAPI (intl)."
            )
            for issue in issues:
                print(f"  • {issue}")
            print(
                "  Чтобы включить Yandex: заполните YANDEX_API_KEY, YANDEX_FOLDER_ID "
                "и LLM_MODEL_RU в .env (см. .env.example).\n"
            )
            region = "intl"
        else:
            hints = "\n  • ".join(issues)
            extra = ""
            if region == "ru" and not _can_fallback_ru_to_intl():
                extra = (
                    "\nЛибо укажите рабочий OPENAI_API_KEY (ProxyAPI) для автоматического "
                    "fallback на intl, либо настройте Yandex полностью."
                )
            raise ValueError(
                "Некорректная конфигурация LLM:\n  • "
                f"{hints}{extra}\n"
                "Либо исправьте .env, либо задайте LLM_REGION=intl и ProxyAPI для всех поездок."
            )

    return _get_llm_cached(region=region)


def get_llm_with_tools(*, city: str = "", llm_region: str | None = None):
    return get_llm(city=city, llm_region=llm_region).bind_tools(TOOLS)


def get_llm_final(*, city: str = "", llm_region: str | None = None):
    # Билеты не в схеме LLM — иначе json_schema ломается на больших tool JSON.
    return (
        get_llm(city=city, llm_region=llm_region)
        .bind(max_tokens=12_288)
        .with_structured_output(ProgramDraft, method="json_schema")
    )

__all__ = [
    "infer_llm_region",
    "get_llm",
    "get_llm_final",
    "get_llm_with_tools",
]
