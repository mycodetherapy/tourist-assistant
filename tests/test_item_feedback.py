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
from program.item_key import make_item_key
from program.parse_items import parse_program_sections
from services.trip_service import TripService


def _sample_routes_program(case_ids: list[str]) -> dict:
    from agents.route_postprocess import format_routes_text
    from models.routes import RouteProgram, RouteStop, TripRouteCase

    cases = [
        TripRouteCase(
            case_id=cid,
            title=f"Маршрут {cid}",
            summary=f"Описание {cid}",
            stops=[
                RouteStop(
                    order=1,
                    kind="leisure",
                    poi_id=f"p-{cid}",
                    narrative=f"Место {cid}",
                )
            ],
            maps_route_url=f"https://yandex.ru/maps/?rtext={cid}",
        )
        for cid in case_ids
    ]
    program = RouteProgram(cases=cases)
    return {
        "tickets": "",
        "routes": program.model_dump(),
        "routes_text": format_routes_text(program),
        "lifehacks": "- Совет",
    }


class TestItemFeedback(unittest.TestCase):
    def setUp(self) -> None:
        self._db_path = "/tmp/test_item_feedback.db"
        os.environ["DATABASE_PATH"] = self._db_path
        if os.path.exists(self._db_path):
            os.remove(self._db_path)
        init_db()
        self.trip_id = create_trip("Москва", "июль 2026", "СПб", "тест")
        self.program = _sample_routes_program(["A", "B", "C"])
        self.version_id = save_itinerary_version(self.trip_id, self.program)
        self.service = TripService()

    def test_upsert_and_list_feedback(self) -> None:
        parsed = parse_program_sections(self.program)
        route_a = parsed.routes.items[0]
        route_b = parsed.routes.items[1]
        upsert_item_feedback(
            self.trip_id,
            self.version_id,
            "routes",
            0,
            make_item_key("routes", route_a),
            1,
        )
        upsert_item_feedback(
            self.trip_id,
            self.version_id,
            "routes",
            1,
            make_item_key("routes", route_b),
            -1,
        )
        votes = list_item_feedback(self.trip_id)
        self.assertEqual(votes[make_item_key("routes", route_a)], 1)
        self.assertEqual(votes[make_item_key("routes", route_b)], -1)

    def test_get_program_view_includes_votes(self) -> None:
        parsed = parse_program_sections(self.program)
        route_text = parsed.routes.items[0]
        self.service.set_item_feedback(
            self.trip_id,
            version_id=self.version_id,
            section="routes",
            item_key=make_item_key("routes", route_text),
            vote=1,
        )
        view = self.service.get_program_view(self.trip_id)
        assert view is not None
        self.assertEqual(view.sections["routes"].items[0].vote, 1)
        self.assertIsNone(view.sections["routes"].items[1].vote)

    def test_votes_cleared_when_rebuilt_item_changes(self) -> None:
        parsed = parse_program_sections(self.program)
        route_text = parsed.routes.items[0]
        self.service.set_item_feedback(
            self.trip_id,
            section="routes",
            item_key=make_item_key("routes", route_text),
            vote=1,
        )
        changed = _sample_routes_program(["X", "B", "C"])
        save_itinerary_version(self.trip_id, changed, scope="routes")
        view = self.service.get_program_view(self.trip_id)
        assert view is not None
        self.assertIsNone(view.sections["routes"].items[0].vote)

    def test_votes_survive_new_program_version(self) -> None:
        parsed = parse_program_sections(self.program)
        route_text = parsed.routes.items[0]
        self.service.set_item_feedback(
            self.trip_id,
            version_id=self.version_id,
            section="routes",
            item_key=make_item_key("routes", route_text),
            vote=1,
        )
        new_version_id = save_itinerary_version(self.trip_id, self.program)
        self.assertNotEqual(new_version_id, self.version_id)
        view = self.service.get_program_view(self.trip_id)
        assert view is not None
        self.assertEqual(view.version_id, new_version_id)
        self.assertEqual(view.sections["routes"].items[0].vote, 1)

    def test_set_item_feedback_validates_item_key(self) -> None:
        with self.assertRaises(ValueError):
            self.service.set_item_feedback(
                self.trip_id,
                version_id=self.version_id,
                section="routes",
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

    def test_stale_key_no_longer_applies_by_index(self) -> None:
        upsert_item_feedback(
            self.trip_id,
            self.version_id,
            "routes",
            0,
            "stale-key-not-in-program",
            1,
        )
        view = self.service.get_program_view(self.trip_id)
        assert view is not None
        self.assertIsNone(view.sections["routes"].items[0].vote)

    def test_unlike_clears_vote(self) -> None:
        parsed = parse_program_sections(self.program)
        key = make_item_key("routes", parsed.routes.items[0])
        self.service.set_item_feedback(
            self.trip_id,
            section="routes",
            item_key=key,
            vote=1,
        )
        self.service.set_item_feedback(
            self.trip_id,
            section="routes",
            item_key=key,
            vote=None,
        )
        view = self.service.get_program_view(self.trip_id)
        assert view is not None
        self.assertIsNone(view.sections["routes"].items[0].vote)

    def test_rebuild_does_not_show_old_like_on_new_route(self) -> None:
        program_v1 = _sample_routes_program(["A", "B", "C"])
        save_itinerary_version(self.trip_id, program_v1, scope="full")
        key_b = make_item_key("routes", parse_program_sections(program_v1).routes.items[1])
        upsert_item_feedback(
            self.trip_id,
            self.version_id,
            "routes",
            1,
            key_b,
            1,
        )
        program_v2 = _sample_routes_program(["A", "X", "Y", "Z"])
        save_itinerary_version(self.trip_id, program_v2, scope="routes")
        view = self.service.get_program_view(self.trip_id)
        assert view is not None
        for item in view.sections["routes"].items:
            if "Вариант X" in item.text or "Вариант Y" in item.text or "Вариант Z" in item.text:
                self.assertIsNone(item.vote)

    def test_set_item_feedback_accepts_item_index(self) -> None:
        self.service.set_item_feedback(
            self.trip_id,
            section="routes",
            item_index=1,
            vote=-1,
        )
        view = self.service.get_program_view(self.trip_id)
        assert view is not None
        self.assertEqual(view.sections["routes"].items[1].vote, -1)

    def test_get_itinerary_version(self) -> None:
        row = get_itinerary_version(self.trip_id, self.version_id)
        assert row is not None
        self.assertEqual(row["trip_id"], self.trip_id)


if __name__ == "__main__":
    unittest.main()
