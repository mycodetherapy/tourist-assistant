"""Тесты HITL-промптов."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from agents.human_review import prompt_approve_program, prompt_reject_action


class TestHumanReview(unittest.TestCase):
    @patch("builtins.input", return_value="")
    def test_approve_empty_enter(self, _input: object) -> None:
        self.assertTrue(prompt_approve_program())

    @patch("builtins.input", return_value="Y")
    def test_approve_latin_y(self, _input: object) -> None:
        self.assertTrue(prompt_approve_program())

    @patch("builtins.input", return_value="y")
    def test_approve_latin_y_lower(self, _input: object) -> None:
        self.assertTrue(prompt_approve_program())

    @patch("builtins.input", return_value="  да  ")
    def test_approve_russian_da(self, _input: object) -> None:
        self.assertTrue(prompt_approve_program())

    @patch("builtins.input", return_value="д")
    def test_approve_russian_d(self, _input: object) -> None:
        self.assertTrue(prompt_approve_program())

    @patch("builtins.input", return_value="н")
    def test_reject_russian_n(self, _input: object) -> None:
        self.assertFalse(prompt_approve_program())

    @patch("builtins.input", return_value="n")
    def test_reject_latin_n(self, _input: object) -> None:
        self.assertFalse(prompt_approve_program())

    @patch("builtins.input", return_value="нет")
    def test_reject_russian_net(self, _input: object) -> None:
        self.assertFalse(prompt_approve_program())

    @patch("builtins.input", side_effect=["нет", ""])
    def test_reject_then_save_draft_on_enter(self, _input: object) -> None:
        self.assertFalse(prompt_approve_program())
        self.assertEqual(prompt_reject_action(), "save_draft")

    @patch("builtins.input", side_effect=["n", "да"])
    def test_reject_then_rebuild(self, _input: object) -> None:
        self.assertFalse(prompt_approve_program())
        self.assertEqual(prompt_reject_action(), "rebuild")


if __name__ == "__main__":
    unittest.main()
