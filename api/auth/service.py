"""Регистрация, вход, BYOK-настройки."""

from __future__ import annotations

import re

from api.auth.crypto import decrypt_secret, encrypt_secret, mask_api_key
from api.auth.jwt_tokens import create_access_token
from api.auth.passwords import hash_password, verify_password
from config.settings import DEFAULT_LLM_BASE_URL, LLM_MODEL, is_placeholder_secret
from db.users import (
    User,
    clear_user_llm_key,
    create_user,
    get_user_by_email,
    get_user_by_google_sub,
    get_user_by_id,
    get_user_settings,
    link_google_sub,
    upsert_user_settings,
)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AuthError(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def _validate_email(email: str) -> str:
    normalized = email.strip().lower()
    if not _EMAIL_RE.match(normalized):
        raise AuthError("Некорректный email")
    return normalized


def _validate_password(password: str) -> None:
    if len(password) < 8:
        raise AuthError("Пароль должен быть не короче 8 символов")


def register_user(*, email: str, password: str) -> tuple[User, str]:
    normalized = _validate_email(email)
    _validate_password(password)
    if get_user_by_email(normalized) is not None:
        raise AuthError("Пользователь с таким email уже существует", status_code=409)
    user = create_user(email=normalized, password_hash=hash_password(password))
    token = create_access_token(user_id=user.id, email=user.email)
    return user, token


def login_user(*, email: str, password: str) -> tuple[User, str]:
    normalized = _validate_email(email)
    user = get_user_by_email(normalized)
    if user is None or not user.password_hash:
        raise AuthError("Неверный email или пароль", status_code=401)
    if not verify_password(password, user.password_hash):
        raise AuthError("Неверный email или пароль", status_code=401)
    token = create_access_token(user_id=user.id, email=user.email)
    return user, token


def login_or_link_google(*, google_sub: str, email: str) -> tuple[User, str]:
    normalized = _validate_email(email)
    by_sub = get_user_by_google_sub(google_sub)
    if by_sub is not None:
        token = create_access_token(user_id=by_sub.id, email=by_sub.email)
        return by_sub, token
    by_email = get_user_by_email(normalized)
    if by_email is not None:
        if by_email.google_sub and by_email.google_sub != google_sub:
            raise AuthError("Email уже привязан к другому Google-аккаунту", status_code=409)
        if not by_email.google_sub:
            link_google_sub(by_email.id, google_sub)
        user = get_user_by_id(by_email.id)
        assert user is not None
        token = create_access_token(user_id=user.id, email=user.email)
        return user, token
    user = create_user(email=normalized, google_sub=google_sub)
    token = create_access_token(user_id=user.id, email=user.email)
    return user, token


def user_from_token_payload(payload: dict[str, object]) -> User:
    sub = payload.get("sub")
    if sub is None:
        raise AuthError("Недействительный токен", status_code=401)
    user = get_user_by_id(int(sub))
    if user is None:
        raise AuthError("Пользователь не найден", status_code=401)
    return user


def save_llm_settings(
    user_id: int,
    *,
    llm_api_key: str | None = None,
    llm_base_url: str | None = None,
    llm_model: str | None = None,
) -> None:
    enc: str | None = None
    if llm_api_key is not None:
        key = llm_api_key.strip()
        if not key:
            raise AuthError("LLM API key не может быть пустым")
        if is_placeholder_secret(key):
            raise AuthError("Укажите реальный ключ OpenRouter, не плейсхолдер")
        try:
            enc = encrypt_secret(key)
        except ValueError as exc:
            raise AuthError(str(exc), status_code=503) from exc
        except RuntimeError as exc:
            raise AuthError(str(exc), status_code=503) from exc
    upsert_user_settings(
        user_id,
        llm_api_key_enc=enc,
        llm_base_url=llm_base_url,
        llm_model=llm_model,
    )


def get_llm_settings_view(user_id: int) -> dict[str, object]:
    row = get_user_settings(user_id)
    configured = bool(row and row.llm_api_key_enc)
    preview: str | None = None
    if configured and row is not None and row.llm_api_key_enc:
        try:
            preview = mask_api_key(decrypt_secret(row.llm_api_key_enc))
        except ValueError:
            preview = "***"
    return {
        "llm_key_configured": configured,
        "llm_key_preview": preview,
        "llm_base_url": (row.llm_base_url if row and row.llm_base_url else DEFAULT_LLM_BASE_URL),
        "llm_model": (row.llm_model if row and row.llm_model else LLM_MODEL),
    }


def require_user_llm_config(user_id: int):
    """Возвращает LlmConfig или бросает AuthError(428)."""
    from agents.llm_context import LlmConfig

    row = get_user_settings(user_id)
    if row is None or not row.llm_api_key_enc:
        raise AuthError(
            "Добавьте ключ OpenRouter в настройках профиля",
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


def remove_llm_key(user_id: int) -> None:
    clear_user_llm_key(user_id)
