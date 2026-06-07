"""Печать финальной программы в консоль."""

from __future__ import annotations

from models.schemas import FinalProgram, is_legacy_program


def print_final_program(program: FinalProgram) -> None:
    """Печатает финальную программу в консоль по разделам."""
    dump = program.model_dump()
    if is_legacy_program(dump):
        sections = [
            ("Билеты", program.tickets),
            ("Мероприятия", program.events),
            ("Питание", program.dining),
            ("Лайфхаки", program.lifehacks),
        ]
    else:
        sections = [
            ("Билеты", program.tickets),
            ("Маршруты", program.routes_text or ""),
            ("Лайфхаки", program.lifehacks),
        ]
    print("\n" + "=" * 60)
    print("КУЛЬТУРНАЯ ПРОГРАММА ПОЕЗДКИ")
    print("=" * 60)
    for title, body in sections:
        print(f"\n--- {title} ---\n")
        print(body)
    print("\n" + "=" * 60)
