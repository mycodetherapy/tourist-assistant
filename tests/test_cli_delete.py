"""Тесты удаления поездки в CLI."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from cli.app import _confirm_delete_trip, _delete_trip_flow
from db import create_trip, init_db, list_trips
from services import TripService


class TestCliDelete(unittest.TestCase):
    def setUp(self) -> None:
        self._db_path = "/tmp/test_cli_delete.db"
        os.environ["DATABASE_PATH"] = self._db_path
        if os.path.exists(self._db_path):
            os.remove(self._db_path)
        init_db()

    @patch("builtins.input", return_value="1")
    def test_confirm_delete_accepts_menu_yes(self, _input: object) -> None:
        self.assertTrue(_confirm_delete_trip(1, city="Новгород", dates="июль 2026"))

    @patch("builtins.input", return_value="2")
    def test_confirm_delete_rejects_menu_no(self, _input: object) -> None:
        self.assertFalse(_confirm_delete_trip(1, city="Новгород", dates="июль 2026"))

    @patch("builtins.input", return_value="y")
    def test_confirm_delete_rejects_letter_input(self, _input: object) -> None:
        """Буква y не подтверждает — только пункт меню «1»."""
        self.assertFalse(_confirm_delete_trip(1, city="Новгород", dates="июль 2026"))

    @patch("builtins.input", side_effect=["1", "1"])
    def test_delete_trip_flow_removes_trip(self, _input: object) -> None:
        trip_id = create_trip("Новгород", "15-18 июля 2026", "Москва", "тест")
        service = TripService()
        _delete_trip_flow(service)
        self.assertEqual(list_trips(), [])


if __name__ == "__main__":
    unittest.main()
