"""Human-in-the-loop: утверждение программы в терминале."""

from __future__ import annotations

import unicodedata

_NO_APPROVE = frozenset({"n", "no", "н", "нет"})
_YES_REBUILD = frozenset({"y", "yes", "д", "да"})


def _normalize_answer(raw: str) -> str:
    text = unicodedata.normalize("NFKC", raw.strip().lower()).replace("ё", "е")
    return text.lstrip("\ufeff")


def prompt_approve_program() -> bool:
    """
    Утвердить программу?
    Enter / да / y — да; н / нет / n — нет.
    Логика «только явный отказ»: иначе при [Да/нет] легко промахнуться по раскладке.
    """
    raw = _normalize_answer(input("Утвердить программу? [Да/нет] (Enter — да): "))
    return raw not in _NO_APPROVE


def prompt_reject_action() -> str:
    """
    После отказа: пересбор целиком или выход без сохранения approved.
    Возвращает 'rebuild' | 'save_draft'.
    """
    print("\nПрограмма не утверждена.")
    raw = _normalize_answer(
        input("Пересобрать снова? [да/Нет] (Enter — сохранить черновик и выйти): ")
    )
    if raw in _YES_REBUILD:
        return "rebuild"
    return "save_draft"
