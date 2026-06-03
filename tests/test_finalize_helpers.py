"""Тесты подготовки finalize (билеты из tool)."""

from __future__ import annotations

import json
import unittest

from langchain_core.messages import ToolMessage

from agents.finalize_helpers import (
    _is_garbage_tickets,
    extract_tickets_summary,
    prepare_finalize_messages,
    resolve_tickets_section,
)
from search.tickets_search import run_tickets_search


class TestFinalizeHelpers(unittest.TestCase):
    def test_garbage_detects_broken_llm_output(self) -> None:
        self.assertTrue(_is_garbage_tickets(":[]"))
        self.assertTrue(_is_garbage_tickets(":{"))

    def test_extract_summary_from_tool(self) -> None:
        payload = run_tickets_search("Москва", "Казань", "10-12 августа 2026")
        messages = [
            ToolMessage(
                content=payload.model_dump_json(),
                tool_call_id="1",
                name="search_roundtrip_tickets",
            )
        ]
        summary = extract_tickets_summary(messages)
        self.assertIsNotNone(summary)
        self.assertIn("Самолёт", summary or "")
        self.assertIn("Поезд", summary or "")

    def test_resolve_falls_back_to_live_search(self) -> None:
        body = resolve_tickets_section(
            messages=[],
            base_program={"tickets": ":[]"},
            origin_city="Москва",
            destination_city="Казань",
            dates="10-12 августа 2026",
            rebuild_scope="full",
        )
        self.assertFalse(_is_garbage_tickets(body))
        self.assertIn("http", body.lower())

    def test_slim_removes_offers_array(self) -> None:
        payload = run_tickets_search("Москва", "Казань", "10-12 августа 2026")
        msg = ToolMessage(
            content=payload.model_dump_json(),
            tool_call_id="1",
            name="search_roundtrip_tickets",
        )
        slimmed = prepare_finalize_messages([msg])[0]
        data = json.loads(str(slimmed.content))
        self.assertNotIn("offers", data)
        self.assertIn("summary_for_llm", data)


if __name__ == "__main__":
    unittest.main()
