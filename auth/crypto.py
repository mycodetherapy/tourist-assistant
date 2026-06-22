"""Шифрование BYOK-ключей (Fernet)."""

from __future__ import annotations

import os

from cryptography.fernet import Fernet, InvalidToken


def validate_fernet_key(raw: str) -> None:
    """Проверяет, что строка — валидный Fernet-ключ (url-safe base64, 32 байта)."""
    key = raw.strip()
    if not key:
        raise ValueError("SETTINGS_ENCRYPTION_KEY не задан")
    try:
        Fernet(key.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise ValueError(
            "SETTINGS_ENCRYPTION_KEY невалиден. Сгенерируйте ключ:\n"
            '  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        ) from exc


def _fernet() -> Fernet:
    raw = os.getenv("SETTINGS_ENCRYPTION_KEY", "").strip()
    validate_fernet_key(raw)
    return Fernet(raw.encode("utf-8"))


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Не удалось расшифровать секрет") from exc


def mask_api_key(api_key: str) -> str:
    key = api_key.strip()
    if len(key) <= 12:
        return "***"
    return f"{key[:7]}...{key[-4:]}"
