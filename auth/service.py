"""BYOK, llm_mode и доступ к прогонам графа."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from auth.crypto import decrypt_secret
from config.settings import DEFAULT_LLM_BASE_URL, LLM_MODEL
from db.users import get_user_settings

LlmMode = Literal["none", "platform", "byok"]
VALID_LLM_MODES: tuple[LlmMode, ...] = ("none", "platform", "byok")

# Оценка стоимости одного AI-прогона для UI (Фаза 2 — wallet).
ESTIMATED_AI_RUN_COST_RUB = 10.0


class AuthError(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class RunContext:
    mode: LlmMode
    llm_config: "LlmConfig | None"


def normalize_llm_mode(raw: str | None) -> LlmMode:
    value = (raw or "none").strip().lower()
    if value in VALID_LLM_MODES:
        return value  # type: ignore[return-value]
    return "none"


def get_user_llm_mode(user_id: int) -> LlmMode:
    row = get_user_settings(user_id)
    if row is None:
        return "none"
    return normalize_llm_mode(row.llm_mode)


def require_user_llm_config(user_id: int):
    """Возвращает LlmConfig или бросает AuthError(428)."""
    from agents.llm_context import LlmConfig

    row = get_user_settings(user_id)
    if row is None or not row.llm_api_key_enc:
        raise AuthError(
            "Добавьте API-ключ LLM в настройках профиля",
            status_code=428,
        )
    try:
        api_key = decrypt_secret(row.llm_api_key_enc)
    except ValueError as exc:
        raise AuthError("Сохранённый LLM-ключ повреждён", status_code=428) from exc
    return LlmConfig(
        api_key=api_key,
        base_url=row.llm_base_url or DEFAULT_LLM_BASE_URL,
        model=row.llm_model or LLM_MODEL,
    )


def resolve_run_context(user_id: int) -> RunContext:
    """
    Режим прогона пользователя:
    - none: алгоритм без LLM;
    - byok: ключ из профиля;
    - platform: оплата из приложения (Фаза 2, пока 503).
    """
    from agents.llm_context import LlmConfig

    mode = get_user_llm_mode(user_id)
    if mode == "none":
        return RunContext(mode="none", llm_config=None)
    if mode == "platform":
        raise AuthError(
            "Оплата AI из приложения скоро будет доступна. "
            "Пока используйте бесплатный режим или свой API-ключ.",
            status_code=503,
        )
    config: LlmConfig = require_user_llm_config(user_id)
    return RunContext(mode="byok", llm_config=config)


def assert_can_start_run(user_id: int) -> LlmMode:
    """Проверяет, можно ли стартовать прогон; возвращает llm_mode."""
    return resolve_run_context(user_id).mode
