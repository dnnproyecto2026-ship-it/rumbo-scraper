"""Tests for the Universidad Austral adapter."""

import unittest

from rumbo_scraper.parsers.austral import (
    UNIVERSITY, _campus_name, build_dataset, discover_programmes, duration_months,
    duration_years, modality, parse_attendance, parse_plan_pdf, parse_plan_pdf_degree,
    plan_document_url,
)
from rumbo_scraper.validators.austral import validate_dataset

KINDS = {12: "Carrera de grado", 21: "Maestría", 14: "Diplomatura", 13: "Programas"}
AREAS = {31: "Derecho", 27: "Biomédicas"}
CAMPUSES = {9: "SEDE PILAR", 10: "SEDE ROSARIO", 8: "SEDE CABA"}


def _product(name: str, url: str, kind: int, area: int = 31, campus: int = 9) -> dict:
    return {"title": {"rendered": name}, "link": url, "tipo-de-producto": [kind],
            "areas-tax": [area], "sedes": [campus]}


class CatalogueTests(unittest.TestCase):
    def test_the_kind_comes_from_the_taxonomy_not_from_the_name(self) -> None:
        refs, _ = discover_programmes(
            [_product("Abogacía", "https://www.austral.edu.ar/a/", 12),
             _product("Maestría en Derecho", "https://www.austral.edu.ar/b/", 21)],
            KINDS, AREAS, CAMPUSES)
        self.assertEqual([(ref.name, ref.level, ref.kind) for ref in refs],
                         [("Abogacía", "Grado", None),
                          ("Maestría en Derecho", "Posgrado", "Maestría")])

    def test_a_kind_outside_the_contract_is_excluded_with_its_reason(self) -> None:
        refs, excluded = discover_programmes(
            [_product("Curso de Finanzas", "https://www.austral.edu.ar/c/", 13)],
            KINDS, AREAS, CAMPUSES)
        self.assertEqual(refs, ())
        self.assertIn("Programas", excluded[0]["motivo"])

    def test_the_area_and_the_campus_come_from_the_taxonomy(self) -> None:
        refs, _ = discover_programmes(
            [_product("Abogacía", "https://www.austral.edu.ar/a/", 12, 31, 10)],
            KINDS, AREAS, CAMPUSES)
        self.assertEqual(refs[0].area, "Derecho")
        self.assertEqual(refs[0].campus, "Sede Rosario")

    def test_an_entry_without_a_name_or_a_link_is_ignored(self) -> None:
        refs, _ = discover_programmes(
            [{"title": {"rendered": ""}, "link": "https://x/", "tipo-de-producto": [12]}],
            KINDS, AREAS, CAMPUSES)
        self.assertEqual(refs, ())


class CampusNameTests(unittest.TestCase):
    def test_reads_the_published_name_and_keeps_an_acronym(self) -> None:
        self.assertEqual(_campus_name("SEDE PILAR"), "Sede Pilar")
        self.assertEqual(_campus_name("SEDE CABA"), "Sede CABA")
        self.assertIsNone(_campus_name(None))


class AttendanceTests(unittest.TestCase):
    HTML = ("<html><body><p>Inicio: 01.03.2027 Duración: 5 Años "
            "Modalidad: Presencial Sede: Pilar</p></body></html>")

    def test_reads_every_labelled_fact(self) -> None:
        self.assertEqual(parse_attendance(self.HTML), {
            "inicio": "01.03.2027", "duracion": "5 Años",
            "modalidad": "Presencial", "sede": "Pilar"})

    def test_converts_the_published_length(self) -> None:
        self.assertEqual(duration_years("5 Años"), 5.0)
        self.assertEqual(duration_months("18 meses"), 18)
        self.assertEqual(duration_months("4 cuatrimestres"), 16)
        self.assertIsNone(duration_years("a confirmar"))

    def test_maps_the_modality_to_the_contract(self) -> None:
        self.assertEqual(modality("Presencial"), "Presencial")
        self.assertEqual(modality("Semipresencial"), "Híbrida")
        self.assertEqual(modality("Online"), "Virtual")
        self.assertIsNone(modality("A confirmar"))


class PlanLinkTests(unittest.TestCase):
    def test_finds_the_download_labelled_as_the_plan(self) -> None:
        html = ('<a href="/?jet_download=abc"><span>Plan de Estudios</span></a>'
                '<a href="/?jet_download=def"><span>Folleto de carrera</span></a>')
        self.assertEqual(plan_document_url(html),
                         "https://www.austral.edu.ar/?jet_download=abc")

    def test_a_page_without_the_plan_yields_nothing(self) -> None:
        self.assertIsNone(plan_document_url('<a href="/?jet_download=x">Folleto</a>'))


class PlanDocumentTests(unittest.TestCase):
    def test_an_unreadable_document_yields_nothing(self) -> None:
        self.assertEqual(parse_plan_pdf(b"no es un pdf", "X"), [])
        self.assertIsNone(parse_plan_pdf_degree(b""))

    def test_the_noise_of_the_chart_is_not_a_subject(self) -> None:
        from rumbo_scraper.parsers.austral import _PLAN_NOISE
        for line in ("PLAN DE ESTUDIOS", "REFERENCIAS", "Primer Cuatrimestre",
                     "Track Ingeniería", "//////", "Electivas"):
            self.assertTrue(_PLAN_NOISE.match(line), line)
        self.assertIsNone(_PLAN_NOISE.match("Análisis matemático I"))


class BuildTests(unittest.TestCase):
    def _refs(self, *products):
        return discover_programmes(list(products), KINDS, AREAS, CAMPUSES)

    def test_one_programme_per_name_and_one_offer_per_campus(self) -> None:
        refs, excluded = self._refs(
            _product("Administración de Empresas", "https://www.austral.edu.ar/pilar/", 12, 31, 9),
            _product("Administración de Empresas", "https://www.austral.edu.ar/rosario/", 12, 31, 10),
        )
        pages = {ref.url: AttendanceTests.HTML for ref in refs}
        dataset = build_dataset(refs, pages, excluded=excluded)
        self.assertEqual(len(dataset["datos"]["carreras"]), 1)
        self.assertEqual({row["sede"] for row in dataset["datos"]["ofertas"]},
                         {"Sede Pilar", "Sede Rosario"})
        self.assertEqual(len(dataset["control_calidad"]["programas_unificados"]), 1)
        validate_dataset(dataset)

    def test_a_page_that_did_not_download_is_excluded_with_its_reason(self) -> None:
        refs, excluded = self._refs(
            _product("Abogacía", "https://www.austral.edu.ar/a/", 12),
            _product("Medicina", "https://www.austral.edu.ar/b/", 12))
        dataset = build_dataset(
            refs, {refs[0].url: AttendanceTests.HTML}, excluded=excluded)
        failed = [row for row in dataset["control_calidad"]["programas_excluidos"]
                  if "descargar" in row["motivo"]]
        self.assertEqual(len(failed), 1)
        validate_dataset(dataset)

    def test_the_campus_of_the_offer_comes_from_the_catalogue(self) -> None:
        refs, excluded = self._refs(
            _product("Abogacía", "https://www.austral.edu.ar/a/", 12, 31, 8))
        dataset = build_dataset(refs, {refs[0].url: AttendanceTests.HTML},
                                excluded=excluded)
        self.assertEqual(dataset["datos"]["ofertas"][0]["sede"], "Sede CABA")
        self.assertEqual(dataset["datos"]["carreras"][0]["facultad_nombre"], "Derecho")
        self.assertEqual(dataset["datos"]["carreras"][0]["universidad_nombre"], UNIVERSITY)

    def test_the_year_of_a_subject_is_never_guessed(self) -> None:
        # The plan charts do not keep their reading order once extracted.
        refs, excluded = self._refs(
            _product("Abogacía", "https://www.austral.edu.ar/a/", 12))
        dataset = build_dataset(refs, {refs[0].url: AttendanceTests.HTML},
                                excluded=excluded)
        self.assertIn("motivo", dataset["control_calidad"]["materias_sin_anio"])


class CampusReferenceTests(unittest.TestCase):
    def test_the_campus_rows_and_the_offers_use_the_same_name(self) -> None:
        refs, excluded = discover_programmes(
            [_product("Abogacía", "https://www.austral.edu.ar/a/", 12, 31, 9)],
            KINDS, AREAS, CAMPUSES)
        dataset = build_dataset(
            refs, {refs[0].url: AttendanceTests.HTML},
            campuses=("SEDE PILAR", "SEDE CABA"), excluded=excluded)
        published = {row["nombre_sede"] for row in dataset["datos"]["sedes"]}
        self.assertEqual(published, {"Sede Pilar", "Sede CABA"})
        self.assertIn(dataset["datos"]["ofertas"][0]["sede"], published)
