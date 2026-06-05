"""Тесты оценок пунктов подборки в SQLite."""

from __future__ import annotations

import os
import unittest

from db import (
    create_trip,
    get_itinerary_version,
    init_db,
    list_item_feedback,
    save_itinerary_version,
    upsert_item_feedback,
)
from services.trip_service import TripService


class TestItemFeedback(unittest.TestCase):
    def setUp(self) -> None:
        self._db_path = "/tmp/test_item_feedback.db"
        os.environ["DATABASE_PATH"] = self._db_path
        if os.path.exists(self._db_path):
            os.remove(self._db_path)
        init_db()
        self.trip_id = create_trip("Москва", "июль 2026", "СПб", "тест")
        self.version_id = save_itinerary_version(
            self.trip_id,
            {
                "tickets": "- Aviasales: url",
                "events": "1. Музей",
                "dining": "1. Кафе",
                "lifehacks": "- Совет",
            },
        )
        self.service = TripService()

    def test_upsert_and_list_feedback(self) -> None:
        from program.item_key import make_item_key

        upsert_item_feedback(
            self.trip_id,
            self.version_id,
            "events",
            0,
            make_item_key("events", "1. Музей"),
            1,
        )
        upsert_item_feedback(
            self.trip_id,
            self.version_id,
            "dining",
            0,
            make_item_key("dining", "1. Кафе"),
            -1,
        )
        votes = list_item_feedback(self.trip_id)
        self.assertEqual(votes[make_item_key("events", "1. Музей")], 1)
        self.assertEqual(votes[make_item_key("dining", "1. Кафе")], -1)

    def test_get_program_view_includes_votes(self) -> None:
        from program.item_key import make_item_key

        self.service.set_item_feedback(
            self.trip_id,
            version_id=self.version_id,
            section="events",
            item_key=make_item_key("events", "1. Музей"),
            vote=1,
        )
        view = self.service.get_program_view(self.trip_id)
        assert view is not None
        self.assertEqual(view.sections["events"].items[0].vote, 1)
        self.assertIsNone(view.sections["dining"].items[0].vote)
        self.assertEqual(view.sections["tickets"].items, ())
        self.assertIn("Aviasales", view.sections["tickets"].intro)

    def test_votes_cleared_when_rebuilt_item_changes(self) -> None:
        from program.item_key import make_item_key

        self.service.set_item_feedback(
            self.trip_id,
            section="events",
            item_key=make_item_key("events", "1. Музей"),
            vote=1,
        )
        save_itinerary_version(
            self.trip_id,
            {
                "tickets": "- Aviasales: url",
                "events": "1. Другой музей",
                "dining": "1. Кафе",
                "lifehacks": "- Совет",
            },
            scope="events",
        )
        view = self.service.get_program_view(self.trip_id)
        assert view is not None
        self.assertIsNone(view.sections["events"].items[0].vote)

    def test_partial_rebuild_keeps_other_sections_votes(self) -> None:
        from program.item_key import make_item_key

        self.service.set_item_feedback(
            self.trip_id,
            section="dining",
            item_key=make_item_key("dining", "1. Кафе"),
            vote=-1,
        )
        self.service.set_item_feedback(
            self.trip_id,
            section="events",
            item_key=make_item_key("events", "1. Музей"),
            vote=1,
        )
        save_itinerary_version(
            self.trip_id,
            {
                "tickets": "- Aviasales: url",
                "events": "1. Новое мероприятие",
                "dining": "1. Кафе",
                "lifehacks": "- Совет",
            },
            scope="events",
        )
        view = self.service.get_program_view(self.trip_id)
        assert view is not None
        self.assertIsNone(view.sections["events"].items[0].vote)
        self.assertEqual(view.sections["dining"].items[0].vote, -1)

    def test_votes_survive_new_program_version(self) -> None:
        from program.item_key import make_item_key

        self.service.set_item_feedback(
            self.trip_id,
            version_id=self.version_id,
            section="events",
            item_key=make_item_key("events", "1. Музей"),
            vote=1,
        )
        new_version_id = save_itinerary_version(
            self.trip_id,
            {
                "tickets": "- Aviasales: url",
                "events": "1. Музей",
                "dining": "1. Кафе",
                "lifehacks": "- Совет",
            },
        )
        self.assertNotEqual(new_version_id, self.version_id)
        view = self.service.get_program_view(self.trip_id)
        assert view is not None
        self.assertEqual(view.version_id, new_version_id)
        self.assertEqual(view.sections["events"].items[0].vote, 1)

    def test_set_item_feedback_validates_item_key(self) -> None:
        with self.assertRaises(ValueError):
            self.service.set_item_feedback(
                self.trip_id,
                version_id=self.version_id,
                section="events",
                item_key="missing-key",
                vote=1,
            )

    def test_tickets_feedback_not_supported(self) -> None:
        with self.assertRaises(ValueError):
            self.service.set_item_feedback(
                self.trip_id,
                version_id=self.version_id,
                section="tickets",  # type: ignore[arg-type]
                item_key="any",
                vote=1,
            )

    def test_votes_fallback_by_index_after_parser_change(self) -> None:
        """Оценка по item_index подтягивается, если item_key устарел."""
        upsert_item_feedback(
            self.trip_id,
            self.version_id,
            "events",
            0,
            "stale-key-not-in-program",
            1,
        )
        view = self.service.get_program_view(self.trip_id)
        assert view is not None
        self.assertEqual(view.sections["events"].items[0].vote, 1)

    def test_set_item_feedback_accepts_item_index(self) -> None:
        self.service.set_item_feedback(
            self.trip_id,
            section="dining",
            item_index=0,
            vote=-1,
        )
        view = self.service.get_program_view(self.trip_id)
        assert view is not None
        self.assertEqual(view.sections["dining"].items[0].vote, -1)

    def test_votes_persist_for_events_with_district_intro(self) -> None:
        from program.item_key import make_item_key

        trip_id = create_trip("Москва", "июль 2026", "СПб", "районы")
        events_text = (
            "Центр, Китай-город\n"
            "1. [Музей A](https://example.com/a)\n"
            "2. [Музей B](https://example.com/b)"
        )
        version_id = save_itinerary_version(
            trip_id,
            {
                "tickets": "- Aviasales: url",
                "events": events_text,
                "dining": "1. Кафе",
                "lifehacks": "- Совет",
            },
        )
        item_key = make_item_key("events", "1. [Музей A](https://example.com/a)")
        self.service.set_item_feedback(
            trip_id,
            version_id=version_id,
            section="events",
            item_key=item_key,
            vote=1,
        )
        view = self.service.get_program_view(trip_id)
        assert view is not None
        self.assertEqual(view.sections["events"].intro, "Центр, Китай-город")
        self.assertEqual(len(view.sections["events"].items), 2)
        self.assertEqual(view.sections["events"].items[0].vote, 1)
        self.assertIsNone(view.sections["events"].items[1].vote)

    def test_get_itinerary_version(self) -> None:
        row = get_itinerary_version(self.trip_id, self.version_id)
        assert row is not None
        self.assertEqual(row["trip_id"], self.trip_id)


if __name__ == "__main__":
    unittest.main()
