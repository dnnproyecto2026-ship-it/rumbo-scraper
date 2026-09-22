"""Negative tests for the official-domain guard."""

import unittest

from rumbo_scraper.normalizers.url import assert_official_url, is_official_url
from rumbo_scraper.validators import validate_contract_urls


class OfficialUrlTests(unittest.TestCase):
    def test_accepts_the_domain_and_its_subdomains(self) -> None:
        self.assertTrue(is_official_url("https://utdt.edu/x", "utdt.edu"))
        self.assertTrue(is_official_url("https://www.utdt.edu/x", "utdt.edu"))
        self.assertTrue(is_official_url("https://images.udesa.edu.ar/a.jpg", "udesa.edu.ar"))

    def test_rejects_a_lookalike_host(self) -> None:
        self.assertFalse(is_official_url("https://utdt.edu.atacante.com/x", "utdt.edu"))
        self.assertFalse(is_official_url("https://noesudesa.edu.ar/x", "udesa.edu.ar"))

    def test_rejects_the_domain_inside_the_query_string(self) -> None:
        self.assertFalse(is_official_url("https://otro-sitio.com/?ref=utdt.edu", "utdt.edu"))
        self.assertFalse(is_official_url("https://otro-sitio.com/utdt.edu/plan", "utdt.edu"))

    def test_rejects_plain_http_and_other_schemes(self) -> None:
        self.assertFalse(is_official_url("http://utdt.edu/x", "utdt.edu"))
        self.assertFalse(is_official_url("javascript:alert(1)", "utdt.edu"))
        self.assertTrue(is_official_url("http://utdt.edu/x", "utdt.edu", require_https=False))

    def test_rejects_empty_and_non_string_values(self) -> None:
        for value in (None, "", "   ", 42, ["https://utdt.edu"]):
            self.assertFalse(is_official_url(value, "utdt.edu"))

    def test_assert_names_the_offending_field(self) -> None:
        with self.assertRaises(ValueError) as error:
            assert_official_url("https://utdt.edu.atacante.com", "utdt.edu", "becas[0].fuente_url")
        self.assertIn("becas[0].fuente_url", str(error.exception))


class ContractUrlTests(unittest.TestCase):
    def test_empty_urls_are_valid_because_the_source_did_not_publish_them(self) -> None:
        validate_contract_urls({"becas": [{"fuente_url": None, "url_postulacion": ""}]}, "utdt.edu")

    def test_a_foreign_url_stops_the_dataset(self) -> None:
        sections = {"becas": [{"fuente_url": "https://utdt.edu.atacante.com/beca"}]}
        with self.assertRaises(ValueError):
            validate_contract_urls(sections, "utdt.edu")

    def test_missing_sections_are_ignored(self) -> None:
        validate_contract_urls({}, "utdt.edu")
