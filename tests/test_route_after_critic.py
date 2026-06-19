"""Маршрутизация после critic."""

import unittest

from agents.nodes import route_after_critic


class TestRouteAfterCritic(unittest.TestCase):
    def test_passed_goes_to_end(self) -> None:
        self.assertEqual(route_after_critic({"critic_passed": True}), "__end__")

    def test_tool_fail_retries_researcher(self) -> None:
        self.assertEqual(
            route_after_critic(
                {
                    "critic_passed": False,
                    "retry_count": 0,
                    "critic_retry_target": "researcher",
                }
            ),
            "researcher",
        )

    def test_program_fail_retries_writer(self) -> None:
        self.assertEqual(
            route_after_critic(
                {
                    "critic_passed": False,
                    "retry_count": 0,
                    "critic_retry_target": "writer",
                }
            ),
            "writer",
        )

    def test_retry_limit_goes_to_end(self) -> None:
        self.assertEqual(
            route_after_critic(
                {
                    "critic_passed": False,
                    "retry_count": 2,
                    "critic_retry_target": "writer",
                }
            ),
            "__end__",
        )


if __name__ == "__main__":
    unittest.main()
