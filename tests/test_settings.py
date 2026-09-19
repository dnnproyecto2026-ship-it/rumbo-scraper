"""Tests for safe Supabase URL normalization."""

import unittest

from rumbo_scraper.normalizers.url import normalize_supabase_url


class SettingsTests(unittest.TestCase):
    def test_keeps_project_url(self) -> None:
        self.assertEqual(
            normalize_supabase_url("https://example.supabase.co/"),
            "https://example.supabase.co",
        )

    def test_removes_rest_api_suffix(self) -> None:
        self.assertEqual(
            normalize_supabase_url("https://example.supabase.co/rest/v1/"),
            "https://example.supabase.co",
        )


if __name__ == "__main__":
    unittest.main()
