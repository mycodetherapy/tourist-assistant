"""BYOK-настройки и LLM config для worker."""

from __future__ import annotations

from auth.crypto import decrypt_secret
from config.settings import DEFAULT_LLM_BASE_URL, LLM_MODEL
from db.users import get_user_settings


class AuthError(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


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
