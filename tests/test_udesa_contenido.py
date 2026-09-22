"""Tests for the UdeSA student-life content pages."""

import unittest

from rumbo_scraper.parsers.udesa import (
    UNIVERSITY, build_content_rows, parse_content_blocks, parse_headed_blocks,
)
from rumbo_scraper.normalizers.url import is_web_url
from rumbo_scraper.validators import external_destinations, validate_contract_urls

SOURCE = "https://udesa.edu.ar/deportes"


class ContentBlockTests(unittest.TestCase):
    def test_reads_a_module_with_a_title_a_body_and_a_link(self) -> None:
        page = {"sections": [{"label": "Blog Deportes", "body": "<p>Conocé las novedades.</p>",
                              "mediaLink": {"linkUri": "/deportes/blog"}}]}
        block = parse_content_blocks(page, SOURCE)[0]
        self.assertEqual(block["titulo"], "Blog Deportes")
        self.assertEqual(block["descripcion"], "Conocé las novedades.")
        self.assertEqual(block["url"], "https://udesa.edu.ar/deportes/blog")
        self.assertEqual(block["fuente_url"], SOURCE)

    def test_reads_the_entries_nested_in_a_module(self) -> None:
        page = {"sections": [{"cards": [{"label": "Torneos", "body": "Internos y externos."}]}]}
        self.assertEqual(parse_content_blocks(page, SOURCE)[0]["titulo"], "Torneos")

    def test_a_module_without_a_body_is_not_a_block(self) -> None:
        self.assertEqual(parse_content_blocks({"sections": [{"label": "Solo título"}]}, SOURCE), [])

    def test_the_same_title_is_kept_once(self) -> None:
        page = {"sections": [{"label": "Torneos", "body": "Uno."}, {"label": "torneos", "body": "Dos."}]}
        self.assertEqual(len(parse_content_blocks(page, SOURCE)), 1)

    def test_a_group_of_people_is_not_content(self) -> None:
        page = {"sections": [{"label": "Directores", "body": "x", "persons": [{"name": "Ana"}]}]}
        self.assertEqual(parse_content_blocks(page, SOURCE), [])


class HeadedBlockTests(unittest.TestCase):
    def test_joins_a_short_heading_with_the_paragraphs_that_follow(self) -> None:
        page = {"sections": [
            {"label": "Jacarandá"},
            {"body": "Esta residencia está a 18 cuadras del Campus."},
            {"body": "Capacidad para 80 estudiantes."},
        ]}
        block = parse_headed_blocks(page, SOURCE)[0]
        self.assertEqual(block["titulo"], "Jacarandá")
        self.assertEqual(block["descripcion"],
                         "Esta residencia está a 18 cuadras del Campus. Capacidad para 80 estudiantes.")

    def test_a_long_sentence_is_prose_and_never_a_heading(self) -> None:
        page = {"sections": [
            {"label": "Jacarandá"},
            {"label": "Los dormis están ubicados dentro del Campus Victoria y son un componente "
                      "esencial de la vida universitaria."},
        ]}
        blocks = parse_headed_blocks(page, SOURCE)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["titulo"], "Jacarandá")

    def test_a_heading_without_paragraphs_is_dropped(self) -> None:
        self.assertEqual(parse_headed_blocks({"sections": [{"label": "Consultas"}]}, SOURCE), [])

    def test_ignores_what_the_paired_reader_already_covers(self) -> None:
        page = {"sections": [{"label": "Torneos", "body": "Internos."}]}
        self.assertEqual(parse_headed_blocks(page, SOURCE), [])


class ContentRowTests(unittest.TestCase):
    BLOCK = {"titulo": "Yale Fox Fellows", "descripcion": "Programa de intercambio.",
             "url": "https://drive.google.com/x", "fuente_url": SOURCE}

    def test_a_scholarship_keeps_unpublished_columns_null(self) -> None:
        row = build_content_rows("becas", "Beca doctoral", [self.BLOCK])[0]
        self.assertEqual(row["nombre_beca"], "Yale Fox Fellows")
        self.assertEqual(row["nivel"], "Posgrado")
        self.assertEqual(row["tipo_beca"], "Beca doctoral")
        for field in ("porcentaje_maximo", "requisitos", "proceso_postulacion",
                      "renovacion", "fecha_cierre", "contacto"):
            self.assertIsNone(row[field], field)

    def test_the_category_comes_from_the_page_not_from_the_text(self) -> None:
        row = build_content_rows("servicios_estudiantiles", "Biblioteca", [self.BLOCK])[0]
        self.assertEqual(row["categoria"], "Biblioteca")
        self.assertEqual(row["universidad_nombre"], UNIVERSITY)

    def test_housing_never_asserts_who_owns_the_building(self) -> None:
        row = build_content_rows("alojamiento", "Residencia", [self.BLOCK])[0]
        self.assertIsNone(row["residencia_propia"])
        self.assertEqual(row["tipo_alojamiento"], "Yale Fox Fellows")


class DestinationUrlTests(unittest.TestCase):
    def test_a_destination_may_leave_the_domain_but_must_be_a_web_address(self) -> None:
        self.assertTrue(is_web_url("https://drive.google.com/drive/folders/1MN"))
        self.assertFalse(is_web_url("javascript:alert(1)"))
        self.assertFalse(is_web_url("/relativa"))
        self.assertFalse(is_web_url(None))

    def test_a_published_link_to_another_domain_is_accepted(self) -> None:
        validate_contract_urls({"servicios_estudiantiles": [
            {"url": "https://drive.google.com/x", "fuente_url": "https://udesa.edu.ar/b"}]},
            "udesa.edu.ar")

    def test_evidence_must_still_be_an_official_page(self) -> None:
        with self.assertRaises(ValueError):
            validate_contract_urls(
                {"becas": [{"fuente_url": "https://drive.google.com/x"}]}, "udesa.edu.ar")

    def test_a_destination_that_is_not_a_web_address_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            validate_contract_urls(
                {"servicios_estudiantiles": [{"url": "javascript:alert(1)"}]}, "udesa.edu.ar")

    def test_external_destinations_are_listed_for_review(self) -> None:
        found = external_destinations({"servicios_estudiantiles": [
            {"url": "https://drive.google.com/x", "fuente_url": "https://udesa.edu.ar/b"}]},
            "udesa.edu.ar")
        self.assertEqual(found, [{"seccion": "servicios_estudiantiles", "campo": "url",
                                  "url": "https://drive.google.com/x"}])
