"""Тесты очистки раздела «Лайфхаки»."""

from __future__ import annotations

import unittest

from agents.lifehacks_quality import (
    build_default_lifehacks,
    clean_lifehacks_display,
    extract_lifehacks_block,
    is_garbage_lifehacks,
)

_SAMPLE_DUMP = """:[]}  Oops, seems like I need to actually fill in the data.

### Events
1. [Музей](https://museumkomi.ru) — выставка

### Dining
1. **Гранат** — [TripAdvisor](https://www.tripadvisor.ru/x)

### Lifehacks
**Day 1**
* Start at the museum
* Walk to lunch

**Transport tips**
* Walking: centre is compact

I've now filled in the data properly.
```json
{
"""


class TestLifehacksQuality(unittest.TestCase):
    def test_detects_full_program_dump(self) -> None:
        self.assertTrue(is_garbage_lifehacks(_SAMPLE_DUMP))

    def test_extract_lifehacks_section(self) -> None:
        block = extract_lifehacks_block(_SAMPLE_DUMP)
        self.assertIn("Day 1", block)
        self.assertNotIn("### Events", block)

    def test_clean_replaces_dump_with_default(self) -> None:
        out = clean_lifehacks_display(_SAMPLE_DUMP, city="Сыктывкар")
        self.assertNotIn("Oops", out)
        self.assertNotIn("tripadvisor", out.lower())
        self.assertIn("Day 1", out)
        self.assertLess(len(out), 1200)

    def test_valid_short_tips_ok(self) -> None:
        tips = "- Утро: музей → обед рядом → вечерняя прогулка.\n- Бронируйте столик заранее."
        self.assertFalse(is_garbage_lifehacks(tips))
        self.assertEqual(clean_lifehacks_display(tips, city="Казань"), tips)

    def test_default_template(self) -> None:
        text = build_default_lifehacks(city="Сыктывкар", walking_area="центр")
        self.assertIn("Сыктывкар", text)
        self.assertNotIn("http", text)


if __name__ == "__main__":
    unittest.main()
