"""Tests for llm_mode / run access."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from auth.service import AuthError, get_user_llm_mode, resolve_run_context
from db.users import UserSettingsRow


class RunAccessTests(unittest.TestCase):
    @patch("auth.service.get_user_settings")
    def test_default_mode_none(self, mock_settings) -> None:
        mock_settings.return_value = None
        self.assertEqual(get_user_llm_mode(1), "none")
        ctx = resolve_run_context(1)
        self.assertEqual(ctx.mode, "none")
        self.assertIsNone(ctx.llm_config)

    @patch("auth.service.get_user_settings")
    def test_platform_not_ready(self, mock_settings) -> None:
        mock_settings.return_value = UserSettingsRow(
            user_id=1,
            llm_api_key_enc=None,
            llm_base_url=None,
            llm_model=None,
            llm_mode="platform",
            updated_at="",
        )
        with self.assertRaises(AuthError) as ctx:
            resolve_run_context(1)
        self.assertEqual(ctx.exception.status_code, 503)


if __name__ == "__main__":
    unittest.main()
