"""Tests for the shared text normalizers."""

import unittest

from rumbo_scraper.normalizers.text import clean_text, comparison_key


class CleanTextTests(unittest.TestCase):
    def test_collapses_whitespace_and_non_breaking_spaces(self) -> None:
        self.assertEqual(clean_text("  Maestría\xa0 en   Economía \n"), "Maestría en Economía")

    def test_a_missing_value_becomes_an_empty_string(self) -> None:
        self.assertEqual(clean_text(None), "")
        self.assertEqual(comparison_key(None), "")


class ComparisonKeyTests(unittest.TestCase):
    def test_removes_accents_and_case(self) -> None:
        self.assertEqual(comparison_key("Administración"), comparison_key("administracion"))

    def test_distinguishes_different_words(self) -> None:
        self.assertNotEqual(comparison_key("Derecho"), comparison_key("Diseño"))
