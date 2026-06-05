"""Тесты стабильного ключа пункта подборки."""

from __future__ import annotations

import unittest

from program.item_key import make_item_key


class TestItemKey(unittest.TestCase):
    def test_same_text_same_key(self) -> None:
        text = "1. [Музей](https://example.com) — выставка"
        self.assertEqual(make_item_key("events", text), make_item_key("events", text))

    def test_whitespace_normalized(self) -> None:
        self.assertEqual(
            make_item_key("events", "Музей  один"),
            make_item_key("events", "музей один"),
        )

    def test_section_part_of_key(self) -> None:
        self.assertNotEqual(
            make_item_key("events", "кафе"),
            make_item_key("dining", "кафе"),
        )


if __name__ == "__main__":
    unittest.main()
