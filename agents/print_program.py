"""Печать финальной программы в консоль."""

from __future__ import annotations

from models.schemas import FinalProgram


def print_final_program(program: FinalProgram) -> None:
    """Печатает финальную программу в консоль по разделам."""
    sections = [
        ("Билеты", program.tickets),
        ("Мероприятия", program.events),
        ("Питание", program.dining),
        ("Лайфхаки", program.lifehacks),
    ]
    print("\n" + "=" * 60)
    print("КУЛЬТУРНАЯ ПРОГРАММА ПОЕЗДКИ")
    print("=" * 60)
    for title, body in sections:
        print(f"\n--- {title} ---\n")
        print(body)
    print("\n" + "=" * 60)
