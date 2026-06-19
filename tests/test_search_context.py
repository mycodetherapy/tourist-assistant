"""Тесты изоляции search/context (ContextVar)."""

from __future__ import annotations

import threading
import unittest

from onboarding.preferences import build_search_context, normalize_trip_preferences
from search.context import (
    bootstrap_from_agent_state,
    clear_search_context,
    get_session_preferences,
    search_context_scope,
    set_session,
)


class SearchContextTests(unittest.TestCase):
    def tearDown(self) -> None:
        clear_search_context()

    def test_context_isolated_between_threads(self) -> None:
        results: dict[str, str | None] = {}
        barrier = threading.Barrier(2)

        def worker(party: str, key: str) -> None:
            prefs = normalize_trip_preferences({"travel_party": party})
            set_session(prefs, build_search_context(prefs))
            barrier.wait()
            current = get_session_preferences()
            results[key] = current.travel_party if current else None
            clear_search_context()

        t1 = threading.Thread(target=worker, args=("solo", "a"))
        t2 = threading.Thread(target=worker, args=("family", "b"))
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        self.assertEqual(results["a"], "solo")
        self.assertEqual(results["b"], "family")

    def test_child_thread_does_not_inherit_context(self) -> None:
        prefs = normalize_trip_preferences({"travel_party": "couple"})
        set_session(prefs, build_search_context(prefs))
        seen: list[object] = []

        def child() -> None:
            seen.append(get_session_preferences())

        thread = threading.Thread(target=child)
        thread.start()
        thread.join()
        self.assertIsNone(seen[0])

    def test_bootstrap_from_agent_state(self) -> None:
        prefs = normalize_trip_preferences({"travel_party": "solo"})
        state = {
            "trip_id": 1,
            "city": "Казань",
            "dates": "3 дня",
            "preferences": prefs.model_dump(),
            "search_context": build_search_context(prefs),
        }
        bootstrap_from_agent_state(state)
        current = get_session_preferences()
        self.assertIsNotNone(current)
        assert current is not None
        self.assertEqual(current.travel_party, "solo")

    def test_search_context_scope_clears(self) -> None:
        prefs = normalize_trip_preferences({"travel_party": "solo"})
        with search_context_scope(
            {
                "trip_id": None,
                "preferences": prefs.model_dump(),
                "search_context": build_search_context(prefs),
            }
        ):
            self.assertIsNotNone(get_session_preferences())
        self.assertIsNone(get_session_preferences())


if __name__ == "__main__":
    unittest.main()
