"""Human-in-the-loop: утверждение программы в терминале."""

from __future__ import annotations


def prompt_approve_program() -> bool:
    """Утвердить программу? Enter = да."""
    raw = input("Утвердить программу? [Y/n]: ").strip().lower()
    if not raw:
        return True
    return raw in {"y", "yes", "д", "да"}


def prompt_reject_action() -> str:
    """
    После отказа: пересбор целиком или выход без сохранения approved.
    Возвращает 'rebuild' | 'save_draft'.
    """
    print("\nПрограмма не утверждена.")
    raw = input(
        "Пересобрать снова? [y/N] (n — сохранить черновик и выйти): "
    ).strip().lower()
    if raw in {"y", "yes", "д", "да"}:
        return "rebuild"
    return "save_draft"
