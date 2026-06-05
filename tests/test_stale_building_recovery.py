"""Тесты восстановления осиротевшего статуса building."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from services.trip_service import TripService


class TestStaleBuildingRecovery(unittest.TestCase):
    def test_recovers_to_approved_when_program_approved(self) -> None:
        service = TripService()
        mock_rm = MagicMock()
        mock_rm.has_active_run_for_trip.return_value = False

        with (
            unittest.mock.patch("services.trip_service.get_trip") as get_trip,
            unittest.mock.patch("services.trip_service.get_latest_itinerary") as latest,
            unittest.mock.patch("services.trip_service.update_trip_status") as upd,
        ):
            get_trip.return_value = {"id": 5, "status": "building"}
            latest.return_value = {"approved": True, "version": 5, "scope": "full", "program": {}}
            result = service.recover_stale_building(5, has_active_run=False)

        self.assertEqual(result, "approved")
        upd.assert_called_once_with(5, "approved")

    def test_skips_when_active_run_exists(self) -> None:
        service = TripService()
        with unittest.mock.patch("services.trip_service.update_trip_status") as upd:
            result = service.recover_stale_building(5, has_active_run=True)
        self.assertIsNone(result)
        upd.assert_not_called()


if __name__ == "__main__":
    unittest.main()
