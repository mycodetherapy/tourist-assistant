"""Тесты подготовки finalize (билеты из tool)."""

from __future__ import annotations

import json
import unittest

from langchain_core.messages import ToolMessage

from models.schemas import ProgramDraft

from agents.finalize_helpers import (
    _coerce_program_draft,
    _is_garbage_tickets,
    build_fallback_program_draft,
    extract_tickets_summary,
    prepare_finalize_messages,
    slim_tool_message_for_finalize,
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

    def test_slim_events_drops_search_blob(self) -> None:
        heavy = {
            "digest": "1. [Музей](https://example.com/m) — выставка",
            "search": {"results": [{"url": "x", "content": "y" * 5000}] * 40},
            "results_count": 40,
        }
        msg = ToolMessage(
            content=json.dumps(heavy, ensure_ascii=False),
            tool_call_id="2",
            name="search_culture_events",
        )
        slim = slim_tool_message_for_finalize(msg)
        data = json.loads(str(slim.content))
        self.assertNotIn("search", data)
        self.assertIn("digest", data)

    def test_prepare_keeps_latest_tool_only(self) -> None:
        old = ToolMessage(
            content=json.dumps({"digest": "старый"}, ensure_ascii=False),
            tool_call_id="a",
            name="search_culture_events",
        )
        new = ToolMessage(
            content=json.dumps({"digest": "новый"}, ensure_ascii=False),
            tool_call_id="b",
            name="search_culture_events",
        )
        out = prepare_finalize_messages([old, new], rebuild_scope="events")
        self.assertEqual(len(out), 1)
        self.assertIn("новый", str(out[0].content))

    def test_fallback_draft_from_digest(self) -> None:
        messages = [
            ToolMessage(
                content=json.dumps(
                    {"digest": "1. [Музей](https://example.com/m) — тест"},
                    ensure_ascii=False,
                ),
                tool_call_id="e",
                name="search_culture_events",
            ),
            ToolMessage(
                content=json.dumps(
                    {"restaurants_digest": "1. [Кафе](https://example.com/c)"},
                    ensure_ascii=False,
                ),
                tool_call_id="d",
                name="search_dining",
            ),
        ]
        draft = build_fallback_program_draft(messages, city="Казань", walking_area="центр")
        self.assertIn("Музей", draft.events)
        self.assertIn("Кафе", draft.dining)
        self.assertFalse(hasattr(draft, "transport"))
        self.assertIn("музей", draft.lifehacks.lower())

    def test_coerce_program_draft_from_parsed_wrapper(self) -> None:
        from unittest.mock import MagicMock

        inner = ProgramDraft(events="Музей", dining="Кафе", lifehacks="Совет")
        wrapper = MagicMock()
        wrapper.parsed = inner
        self.assertEqual(_coerce_program_draft(wrapper).events, "Музей")
        self.assertEqual(_coerce_program_draft(inner).dining, "Кафе")

    def test_invoke_fallback_passes_city(self) -> None:
        from unittest.mock import MagicMock

        from agents.finalize_helpers import invoke_program_draft
        from langchain_core.messages import HumanMessage, SystemMessage

        class LengthErr(Exception):
            pass

        llm = MagicMock()
        llm.invoke.side_effect = LengthErr(
            "Could not parse response content as the length limit was reached"
        )
        messages = [
            ToolMessage(
                content=json.dumps(
                    {"digest": "1. [Музей](https://example.com/m)"},
                    ensure_ascii=False,
                ),
                tool_call_id="e",
                name="search_culture_events",
            ),
        ]
        draft = invoke_program_draft(
            llm,
            system=SystemMessage(content="test"),
            tool_messages=[],
            human=HumanMessage(content="test"),
            state_messages=messages,
            city="Казань",
        )
        self.assertIn("Музей", draft.events)


if __name__ == "__main__":
    unittest.main()
