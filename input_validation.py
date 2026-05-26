"""Валидация и санитизация пользовательского ввода из CLI."""

from __future__ import annotations

from config import settings


def sanitize_and_validate(text: str, field_name: str) -> str:
    """
    Очищает и проверяет пользовательский ввод на инъекции и чрезмерную длину.
    Возвращает нормализованную строку или выбрасывает ValueError.
    """
    cleaned = text.strip()
    if not cleaned:
        raise ValueError(f"Поле «{field_name}» не может быть пустым.")

    max_len = settings.MAX_LENGTHS.get(field_name, 2000)
    if len(cleaned) > max_len:
        raise ValueError(
            f"Поле «{field_name}» слишком длинное (максимум {max_len} символов)."
        )

    for pattern in settings.INJECTION_PATTERNS:
        if pattern.search(cleaned):
            raise ValueError(
                f"Поле «{field_name}» содержит подозрительные конструкции и отклонено."
            )

    return cleaned
