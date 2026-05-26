"""Eval smoke без LLM."""

from __future__ import annotations

import unittest

from eval.run import main


class TestEval(unittest.TestCase):
    def test_smoke_suite_passes(self) -> None:
        code = main(["--suite", "smoke"])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
