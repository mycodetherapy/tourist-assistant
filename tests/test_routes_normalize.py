"""Нормализация алиасов LLM в контракте маршрутов."""

from __future__ import annotations

import unittest

from models.routes import RouteProgram, TripRouteCase, normalize_routes_draft_payload
from models.schemas import RoutesDraft

from agents.finalize_helpers import _coerce_routes_draft


class TestRoutesNormalize(unittest.TestCase):
    def test_trip_route_case_accepts_route_id_aliases(self) -> None:
        case = TripRouteCase.model_validate(
            {
                "route_id": "A",
                "route_title": "Музыка и время",
                "route_summary": "Короткая прогулка по центру",
                "stops": [],
            }
        )
        self.assertEqual(case.case_id, "A")
        self.assertEqual(case.title, "Музыка и время")
        self.assertEqual(case.summary, "Короткая прогулка по центру")

    def test_routes_draft_from_llm_aliases(self) -> None:
        payload = {
            "routes": {
                "cases": [
                    {
                        "route_id": "A",
                        "route_title": "Музыка и время",
                        "route_summary": "Коротко",
                        "stops": [],
                    },
                    {
                        "route_id": "B",
                        "route_title": "Центр (Ярославль)",
                        "route_summary": "Средне",
                        "stops": [],
                    },
                    {
                        "route_id": "C",
                        "route_title": "Толchково",
                        "route_summary": "Длинно",
                        "stops": [],
                    },
                ]
            }
        }
        draft = RoutesDraft(**normalize_routes_draft_payload(payload))
        self.assertEqual([c.case_id for c in draft.routes.cases], ["A", "B", "C"])
        self.assertEqual(draft.routes.cases[1].title, "Центр (Ярославль)")

    def test_coerce_routes_draft_repairs_dict(self) -> None:
        raw = {
            "routes": {
                "cases": [
                    {
                        "route_id": "A",
                        "route_title": "Лёгкий",
                        "route_summary": "",
                        "stops": [],
                    }
                ]
            }
        }
        draft = _coerce_routes_draft(raw)
        self.assertEqual(draft.routes.cases[0].case_id, "A")

    def test_route_program_accepts_cases_list(self) -> None:
        program = RouteProgram.model_validate(
            [
                {
                    "route_id": "A",
                    "route_title": "A",
                    "route_summary": "",
                    "stops": [],
                }
            ]
        )
        self.assertEqual(program.cases[0].case_id, "A")


if __name__ == "__main__":
    unittest.main()
