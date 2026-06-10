"""Тесты очистки digest мероприятий."""

from __future__ import annotations

import unittest

from search.digest_format import (
    format_event_entry,
    format_events_digest,
    is_aggregator_events_url,
    linkify_event_line,
    rank_events_results,
    sanitize_snippet,
)


class TestDigestFormat(unittest.TestCase):
    def test_sanitize_removes_template_junk(self) -> None:
        raw = "{{ msg }}\nРазмер шрифта: +\nМузей Коми — выставка стерляди до 2026."
        out = sanitize_snippet(raw)
        self.assertNotIn("{{", out)
        self.assertIn("стерляди", out)

    def test_aggregator_url_detected(self) -> None:
        self.assertTrue(
            is_aggregator_events_url("https://www.afisha.ru/syktyvkar/events")
        )
        self.assertFalse(
            is_aggregator_events_url("https://museumkomi.ru?cat=3")
        )

    def test_markdown_link_in_entry(self) -> None:
        line = format_event_entry(
            1,
            "Национальный музей Республики Коми",
            "https://museumkomi.ru?cat=3",
            "29.01–03.05.2026 выставка Есенина",
        )
        self.assertIn("[", line)
        self.assertIn("](https://museumkomi.ru?cat=3)", line)
        self.assertNotIn(" — https://", line)

    def test_linkify_plain_url_line(self) -> None:
        raw = (
            "1. Национальный музей — https://www.culture.ru/institutes/10082/x. "
            "Национальный музей — описание"
        )
        out = linkify_event_line(raw)
        self.assertIn("](https://www.culture.ru/institutes/10082/x)", out)
        self.assertNotIn(" — https://", out)

    def test_format_events_digest_compact(self) -> None:
        results = [
            {
                "title": "Афиша выставок",
                "url": "https://www.afisha.ru/syktyvkar/exhibitions",
                "snippet": "купить билеты " * 50,
            },
            {
                "title": "Выставка стерляди",
                "url": "https://museumkomi.ru?cat=3",
                "snippet": "29.01.2026 - 03.05.2026 выставка о стерляди.",
            },
            {
                "title": "НГРК выставки",
                "url": "https://www.ngrkomi.ru/gallery/exhibition",
                "snippet": "Русское классическое искусство до 2026.",
            },
        ]
        digest = format_events_digest(results)
        self.assertNotIn("{{", digest)
        self.assertIn("](https://museumkomi.ru?cat=3)", digest)
        self.assertLessEqual(len(digest.splitlines()), 12)


if __name__ == "__main__":
    unittest.main()
