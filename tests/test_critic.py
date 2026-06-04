"""Тесты critic без LLM."""

from __future__ import annotations

import unittest

from agents.critic import run_critic
from langchain_core.messages import ToolMessage


class TestCritic(unittest.TestCase):
    def test_passes_with_tools_and_links(self) -> None:
        state = {
            "rebuild_scope": "full",
            "messages": [
                ToolMessage(content="{}", tool_call_id="1", name="search_roundtrip_tickets"),
                ToolMessage(content="{}", tool_call_id="2", name="search_culture_events"),
                ToolMessage(
                    content="{}",
                    tool_call_id="3",
                    name="search_dining",
                ),
            ],
            "program": {
                "tickets": (
                    "Самолёт: рейс SU https://avia.example/a\n"
                    "Поезд: плацкарт https://rzd.example/b\n"
                    "Автобус: междугородний https://bus.example/c\n"
                ),
                "events": (
                    "Эрмитаж — музей https://hermitagemuseum.org\n"
                    "Русский музей — выставки https://rusmuseum.ru\n"
                ),
                "dining": "\n".join(
                    f"Ресторан {i} https://dining.example/r{i}" for i in range(7)
                ),
                "lifehacks": "Маршрут: музей утром → обед рядом → вечерний театр пешком.",
            },
        }
        passed, _ = run_critic(state)
        self.assertTrue(passed)


if __name__ == "__main__":
    unittest.main()
