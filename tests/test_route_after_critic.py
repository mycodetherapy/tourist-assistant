"""Маршрутизация после critic: END или retry researcher."""

import unittest

from agents.nodes import route_after_critic


class TestRouteAfterCritic(unittest.TestCase):
    def test_passed_goes_to_end(self) -> None:
        self.assertEqual(route_after_critic({"critic_passed": True}), "__end__")

    def test_failed_retries_researcher(self) -> None:
        self.assertEqual(
            route_after_critic({"critic_passed": False, "retry_count": 0}),
            "researcher",
        )

    def test_retry_limit_goes_to_end(self) -> None:
        self.assertEqual(
            route_after_critic({"critic_passed": False, "retry_count": 2}),
            "__end__",
        )


if __name__ == "__main__":
    unittest.main()
