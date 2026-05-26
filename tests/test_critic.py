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
                    name="search_dining_and_transport",
                ),
            ],
            "program": {
                "tickets": "✈️ 🚂 🚌",
                "dining": " ".join(f"https://x{i}.ru" for i in range(7)),
            },
        }
        passed, _ = run_critic(state)
        self.assertTrue(passed)


if __name__ == "__main__":
    unittest.main()
