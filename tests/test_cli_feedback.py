"""Тесты CLI-оценок пунктов программы."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from cli.feedback import (
    _parse_vote_command,
    offer_feedback_before_review,
    run_feedback_session,
)
from db import create_trip, init_db, save_itinerary_version
from services.trip_service import TripService


class TestCliFeedbackParsing(unittest.TestCase):
    def test_parse_like(self) -> None:
        self.assertEqual(_parse_vote_command("0 +"), (0, 1))

    def test_parse_dislike(self) -> None:
        self.assertEqual(_parse_vote_command("2 -"), (2, -1))

    def test_parse_clear(self) -> None:
        self.assertEqual(_parse_vote_command("1 0"), (1, None))

    def test_parse_invalid(self) -> None:
        self.assertIsNone(_parse_vote_command("like"))


class TestCliFeedbackSession(unittest.TestCase):
    def setUp(self) -> None:
        self._db_path = "/tmp/test_cli_feedback.db"
        os.environ["DATABASE_PATH"] = self._db_path
        if os.path.exists(self._db_path):
            os.remove(self._db_path)
        init_db()
        self.trip_id = create_trip("Москва", "июль 2026", "СПб", "тест")
        self.program = {
            "tickets": "- Aviasales: url",
            "events": "1. Музей\n2. Парк",
            "dining": "1. Кафе",
            "lifehacks": "1. Совет один\n2. Совет два",
        }
        save_itinerary_version(self.trip_id, self.program)
        self.service = TripService()

    @patch("builtins.input", side_effect=["", ""])
    def test_run_feedback_session_exits_on_enter(self, _input: object) -> None:
        run_feedback_session(self.service, self.trip_id)

    @patch("builtins.input", side_effect=["", ""])
    def test_offer_skips_when_user_declines(self, _input: object) -> None:
        offer_feedback_before_review(
            self.service,
            self.trip_id,
            program_data=self.program,
            scope="full",
        )

    @patch("builtins.input", side_effect=["да", "3", "0 +", "", ""])
    def test_offer_and_vote_before_review(self, _input: object) -> None:
        offer_feedback_before_review(
            self.service,
            self.trip_id,
            program_data=self.program,
            scope="full",
        )
        view = self.service.build_program_view(self.trip_id, self.program)
        self.assertEqual(view.sections["events"].items[0].vote, 1)

    @patch("builtins.input", side_effect=["3", "0 +", "", ""])
    def test_vote_with_program_data_before_db_version(self, _input: object) -> None:
        trip_id = create_trip("Казань", "август 2026", "Москва", "новая")
        program = {
            "tickets": "- билет",
            "events": "1. Новый музей",
            "dining": "1. Ресторан",
            "lifehacks": "- совет",
        }
        run_feedback_session(
            self.service,
            trip_id,
            program_data=program,
            scope="full",
        )
        view = self.service.build_program_view(trip_id, program)
        self.assertEqual(view.sections["events"].items[0].vote, 1)


if __name__ == "__main__":
    unittest.main()
