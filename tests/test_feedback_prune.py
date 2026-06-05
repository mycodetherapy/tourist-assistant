"""Тесты сброса оценок после пересборки."""

from __future__ import annotations

import unittest

from program.feedback_prune import find_stale_feedback_keys
from program.item_key import make_item_key


class TestFeedbackPrune(unittest.TestCase):
    def test_stale_key_when_text_changed(self) -> None:
        old_key = make_item_key("events", "1. Музей")
        program = {
            "tickets": "- x",
            "events": "1. Другой музей",
            "dining": "1. Кафе",
            "lifehacks": "- совет",
        }
        stale = find_stale_feedback_keys(
            program,
            "events",
            existing=[("events", old_key)],
        )
        self.assertEqual(stale, [("events", old_key)])

    def test_keeps_unchanged_key(self) -> None:
        key = make_item_key("events", "1. Музей")
        program = {
            "tickets": "- x",
            "events": "1. Музей",
            "dining": "1. Кафе",
            "lifehacks": "- совет",
        }
        stale = find_stale_feedback_keys(
            program,
            "full",
            existing=[("events", key), ("dining", make_item_key("dining", "1. Кафе"))],
        )
        self.assertEqual(stale, [])

    def test_tickets_scope_does_not_prune(self) -> None:
        key = make_item_key("events", "1. Музей")
        program = {
            "tickets": "- новый билет",
            "events": "1. Музей",
            "dining": "1. Кафе",
            "lifehacks": "- совет",
        }
        stale = find_stale_feedback_keys(
            program,
            "tickets",
            existing=[("events", key)],
        )
        self.assertEqual(stale, [])


if __name__ == "__main__":
    unittest.main()
