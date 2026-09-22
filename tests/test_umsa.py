"""Tests for the UMSA adapter."""

import unittest

from rumbo_scraper.parsers.umsa import (
    UNIVERSITY, build_dataset, discover_programmes, duration_months, duration_years,
    modality, parse_labelled_columns, parse_labelled_text, parse_study_plan,
)
from rumbo_scraper.validators.umsa import validate_dataset

TITLES = {269: "Grado", 270: "Posgrado", 271: "Pregrado"}
POSTGRADUATE = {275: "Doctorados", 276: "Maestrías", 277: "Especializaciones"}
FACULTIES = {259: "Ciencias Jurídicas y Sociales", 260: "Ciencias Económicas"}
OFFERS = {248: "Diplomatura", 250: "Curso", 267: "Taller"}


def _career(name: str, url: str, title: int, kind: int | None = None) -> dict:
    row = {"title": {"rendered": name}, "link": url, "tipo-de-titulo": [title],
           "facultad": [259]}
    if kind:
        row["tipo-de-posgrado"] = [kind]
    return row


def _offer(name: str, url: str, kind: int) -> dict:
    return {"title": {"rendered": name}, "link": url, "tipo-de-oferta": [kind],
            "facultad": [260]}


class CatalogueTests(unittest.TestCase):
    def test_the_level_comes_from_the_title_taxonomy(self) -> None:
        refs, _ = discover_programmes(
            [_career("Abogacía", "https://www.umsa.edu.ar/a/", 269),
             _career("Doctorado en Derecho", "https://www.umsa.edu.ar/b/", 270, 275)],
            [], TITLES, POSTGRADUATE, FACULTIES, OFFERS)
        self.assertEqual([(r.name, r.level, r.kind) for r in refs],
                         [("Abogacía", "Grado", None),
                          ("Doctorado en Derecho", "Posgrado", "Doctorado")])

    def test_the_plural_of_the_taxonomy_maps_to_the_contract(self) -> None:
        refs, _ = discover_programmes(
            [_career("Maestría X", "https://www.umsa.edu.ar/m/", 270, 276),
             _career("Especialización Y", "https://www.umsa.edu.ar/e/", 270, 277)],
            [], TITLES, POSTGRADUATE, FACULTIES, OFFERS)
        self.assertEqual({r.kind for r in refs}, {"Maestría", "Especialización"})

    def test_only_a_diplomatura_of_the_offers_is_a_postgraduate(self) -> None:
        refs, excluded = discover_programmes(
            [], [_offer("Diplomatura en IA", "https://www.umsa.edu.ar/d/", 248),
                 _offer("Curso de Excel", "https://www.umsa.edu.ar/c/", 250),
                 _offer("Taller de Teatro", "https://www.umsa.edu.ar/t/", 267)],
            TITLES, POSTGRADUATE, FACULTIES, OFFERS)
        self.assertEqual([(r.name, r.kind) for r in refs],
                         [("Diplomatura en IA", "Diplomatura")])
        self.assertEqual(len(excluded), 2)
        self.assertIn("Curso", excluded[0]["motivo"] + excluded[1]["motivo"])

    def test_a_level_outside_the_contract_is_excluded_with_its_reason(self) -> None:
        refs, excluded = discover_programmes(
            [_career("Tecnicatura", "https://www.umsa.edu.ar/t/", 271)],
            [], TITLES, POSTGRADUATE, FACULTIES, OFFERS)
        self.assertEqual(refs, ())
        self.assertIn("Pregrado", excluded[0]["motivo"])

    def test_the_faculty_comes_from_the_taxonomy(self) -> None:
        refs, _ = discover_programmes(
            [_career("Abogacía", "https://www.umsa.edu.ar/a/", 269)],
            [], TITLES, POSTGRADUATE, FACULTIES, OFFERS)
        self.assertEqual(refs[0].faculty, "Ciencias Jurídicas y Sociales")


class LabelledTests(unittest.TestCase):
    COLUMNS = ('<div class="row"><div class="col">Duración</div>'
               '<div class="col">Título</div></div>'
               '<div class="row"><div class="col">2 años de cursada</div>'
               '<div class="col">Doctor/a en Ciencias Jurídicas</div></div>')

    def test_pairs_the_header_row_with_the_values_below_it(self) -> None:
        self.assertEqual(parse_labelled_columns(self.COLUMNS), {
            "duracion": "2 años de cursada",
            "titulo": "Doctor/a en Ciencias Jurídicas"})

    def test_a_header_without_values_yields_nothing(self) -> None:
        html = '<div class="row"><div class="col">Duración</div><div class="col">Título</div></div>'
        self.assertEqual(parse_labelled_columns(html), {})

    def test_reads_a_label_written_without_a_colon(self) -> None:
        html = "<p>MODALIDAD A distancia Duración: 2 años CONOCÉ LA EDITORIAL</p>"
        self.assertEqual(parse_labelled_text(html, "MODALIDAD"), "A distancia")
        self.assertEqual(parse_labelled_text(html, "Duración"), "2 años")

    def test_converts_the_published_length(self) -> None:
        self.assertEqual(duration_years("5 años"), 5.0)
        self.assertEqual(duration_months("18 meses"), 18)
        self.assertEqual(duration_months("1 mes"), 1)
        self.assertEqual(duration_months("2 años"), 24)
        self.assertIsNone(duration_months("a definir"))

    def test_maps_the_modality_to_the_contract(self) -> None:
        self.assertEqual(modality("A distancia"), "Virtual")
        self.assertEqual(modality("Presencial o Virtual"), "Híbrida")
        self.assertEqual(modality("Presencial"), "Presencial")
        self.assertIsNone(modality(None))


class StudyPlanTests(unittest.TestCase):
    def _plan(self, heading: str, rows: str) -> str:
        return f"<p>{heading}</p><table>{rows}</table>"

    def test_reads_the_year_named_in_words(self) -> None:
        html = self._plan("PRIMER AÑO",
                          "<tr><td>Derecho Privado</td><td>Cuatrimestral</td></tr>")
        row = parse_study_plan(html, "Abogacía")[0]
        self.assertEqual(row["anio_cursada"], 1)
        self.assertEqual(row["regimen"], "Cuatrimestral")
        self.assertEqual(row["nombre_materia"], "Derecho Privado")

    def test_reads_the_year_named_in_digits(self) -> None:
        html = self._plan("CICLO DE FORMACIÓN GENERAL (1 AÑO)",
                          "<tr><td>Filosofía del derecho</td></tr>")
        self.assertEqual(parse_study_plan(html, "Doctorado")[0]["anio_cursada"], 1)

    def test_a_cycle_without_a_year_leaves_it_null(self) -> None:
        html = self._plan("CICLO DE FORMACIÓN ESPECÍFICA",
                          "<tr><td>Derecho Penal</td></tr>")
        self.assertIsNone(parse_study_plan(html, "Doctorado")[0]["anio_cursada"])

    def test_a_repeated_subject_of_the_same_year_is_kept_once(self) -> None:
        html = self._plan("PRIMER AÑO",
                          "<tr><td>Derecho Privado</td></tr><tr><td>DERECHO PRIVADO</td></tr>")
        self.assertEqual(len(parse_study_plan(html, "Abogacía")), 1)

    def test_a_page_without_tables_yields_nothing(self) -> None:
        self.assertEqual(parse_study_plan("<p>Sin plan</p>", "X"), [])


class BuildTests(unittest.TestCase):
    def test_a_programme_published_twice_becomes_one_row(self) -> None:
        refs, excluded = discover_programmes(
            [], [_offer("Diplomatura en IA", "https://www.umsa.edu.ar/d1/", 248),
                 _offer("Diplomatura en IA", "https://www.umsa.edu.ar/d2/", 248)],
            TITLES, POSTGRADUATE, FACULTIES, OFFERS)
        pages = {ref.url: "<p>MODALIDAD Presencial</p>" for ref in refs}
        dataset = build_dataset(refs, pages, excluded=excluded)
        self.assertEqual(len(dataset["datos"]["posgrados"]), 1)
        self.assertEqual(len(dataset["control_calidad"]["programas_unificados"]), 1)
        validate_dataset(dataset)

    def test_a_page_that_did_not_download_is_excluded_with_its_reason(self) -> None:
        refs, excluded = discover_programmes(
            [_career("Abogacía", "https://www.umsa.edu.ar/a/", 269),
             _career("Medicina", "https://www.umsa.edu.ar/b/", 269)],
            [], TITLES, POSTGRADUATE, FACULTIES, OFFERS)
        dataset = build_dataset(refs, {refs[0].url: "<p>x</p>"}, excluded=excluded)
        failed = [r for r in dataset["control_calidad"]["programas_excluidos"]
                  if "descargar" in r["motivo"]]
        self.assertEqual(len(failed), 1)
        validate_dataset(dataset)

    def test_the_degree_row_carries_what_the_page_publishes(self) -> None:
        refs, excluded = discover_programmes(
            [_career("Abogacía", "https://www.umsa.edu.ar/a/", 269)],
            [], TITLES, POSTGRADUATE, FACULTIES, OFFERS)
        html = ("<p>MODALIDAD Presencial Duración: 5 años CONOCÉ</p>"
                "<p>PRIMER AÑO</p><table><tr><td>Derecho Privado</td></tr></table>")
        dataset = build_dataset(refs, {refs[0].url: html}, excluded=excluded)
        career = dataset["datos"]["carreras"][0]
        self.assertEqual(career["universidad_nombre"], UNIVERSITY)
        self.assertEqual(career["duracion_anios"], 5.0)
        self.assertEqual(career["cantidad_materias_total"], 1)
        self.assertEqual(dataset["datos"]["ofertas"][0]["modalidad"], "Presencial")
