"""Tests for the Universidad de Belgrano adapter."""

import unittest

from rumbo_scraper.parsers.ub import (
    BASE_URL, UNIVERSITY, build_dataset, discover_programmes, duration_months,
    duration_years, faculty_name, modality, parse_fact_sheet, parse_inline_facts,
    parse_plan_pdf, plan_document_url, postgraduate_kind, subject_count,
)
from rumbo_scraper.validators.ub import validate_dataset

GRADO_INDEX = f"{BASE_URL}/distribucion-carreras-de-grado"
POSGRADO_INDEX = f"{BASE_URL}/distribucion-carreras-de-posgrados"
CAREER = f"{BASE_URL}/facultad-de-derecho-y-ciencias-sociales/abogacia"

SHEET = ("<table>"
         "<tr><td>TÍTULO FINAL</td><td>Abogado</td></tr>"
         "<tr><td>GRADO ACADÉMICO</td><td>Grado</td></tr>"
         "<tr><td>TÍTULO INTERMEDIO</td><td>Procurador</td></tr>"
         "<tr><td>MODALIDAD</td><td>Presencial</td></tr>"
         "<tr><td>EXTENSIÓN</td><td>4 años</td></tr>"
         "<tr><td>CANTIDAD DE MATERIAS</td><td>42</td></tr>"
         "<tr><td>TURNO</td><td>Mañana - Tarde</td></tr>"
         "<tr><td>ACREDITACIÓN DE CONEAU</td><td>Nº 459/20</td></tr>"
         "</table>")


class DiscoveryTests(unittest.TestCase):
    def test_the_level_comes_from_the_list_the_link_was_on(self) -> None:
        refs = discover_programmes({
            GRADO_INDEX: [(CAREER, "ABOGACÍA")],
            POSGRADO_INDEX: [(f"{BASE_URL}/escuela-de-posgrado-en-derecho/maestria", "MAESTRÍA")],
        })
        self.assertEqual({r.name: r.level for r in refs},
                         {"Abogacía": "Grado", "Maestría": "Posgrado"})

    def test_the_names_are_published_in_capitals_and_read_back(self) -> None:
        refs = discover_programmes({GRADO_INDEX: [(CAREER, "LICENCIATURA EN COMERCIO EXTERIOR")]})
        self.assertEqual(refs[0].name, "Licenciatura en Comercio Exterior")

    def test_a_link_outside_a_faculty_is_not_a_programme(self) -> None:
        self.assertEqual(discover_programmes({GRADO_INDEX: [(f"{BASE_URL}/ingreso", "X")]}), ())

    def test_the_faculty_comes_from_the_path(self) -> None:
        refs = discover_programmes({GRADO_INDEX: [(CAREER, "ABOGACÍA")]})
        self.assertEqual(refs[0].faculty, "Facultad de Derecho y Ciencias Sociales")
        self.assertEqual(faculty_name("escuela-de-posgrado-en-negocios"),
                         "Escuela de Posgrado en Negocios")


class FactTests(unittest.TestCase):
    def test_reads_every_row_of_the_sheet(self) -> None:
        facts = parse_fact_sheet(SHEET)
        self.assertEqual(facts["titulo_final"], "Abogado")
        self.assertEqual(facts["extension"], "4 años")
        self.assertEqual(facts["coneau"], "Nº 459/20")
        self.assertEqual(facts["turno"], "Mañana - Tarde")

    def test_a_page_without_the_sheet_yields_nothing(self) -> None:
        self.assertEqual(parse_fact_sheet("<p>Consultorio contable</p>"), {})

    def test_reads_the_facts_a_postgraduate_states_in_a_sentence(self) -> None:
        html = ("<p>Modalidad de cursada Duración: 2 años (4 cuatrimestres) "
                "Modalidad: Blended (25% Híbrido + 75% Virtual) Días de cursada "
                "Acreditación de CONEAU Nº 106/21. RM Validez Nº 192/21.</p>")
        facts = parse_inline_facts(html)
        self.assertEqual(facts["extension"], "2 años (4 cuatrimestres)")
        self.assertEqual(facts["coneau"], "Nº 106/21")
        self.assertEqual(modality(facts["modalidad"]), "Híbrida")

    def test_converts_what_the_sheet_states(self) -> None:
        self.assertEqual(duration_years("4 años"), 4.0)
        self.assertEqual(duration_months("2 años (4 cuatrimestres)"), 24)
        self.assertEqual(subject_count("42"), 42)
        self.assertIsNone(subject_count("a confirmar"))

    def test_recognises_the_kind_of_postgraduate(self) -> None:
        self.assertEqual(postgraduate_kind("Maestría en Fintech"), "Maestría")
        self.assertEqual(postgraduate_kind("Doctorado en Ciencia Política"), "Doctorado")
        self.assertIsNone(postgraduate_kind("Programa raro"))


class PlanTests(unittest.TestCase):
    def test_finds_the_document_labelled_as_the_plan(self) -> None:
        html = ('<a href="/sites/default/files/GRADO_Abogacia_plan.pdf">PLAN DE ESTUDIOS</a>'
                '<a href="/otros.pdf">CONTENIDOS</a>')
        self.assertEqual(plan_document_url(html),
                         f"{BASE_URL}/sites/default/files/GRADO_Abogacia_plan.pdf")

    def test_a_page_without_the_document_yields_nothing(self) -> None:
        self.assertIsNone(plan_document_url('<a href="#">PLAN DE ESTUDIOS</a>'))

    def test_an_unreadable_document_yields_nothing(self) -> None:
        self.assertEqual(parse_plan_pdf(b"no es un pdf", "X"), [])


class BuildTests(unittest.TestCase):
    def _refs(self):
        return discover_programmes({GRADO_INDEX: [(CAREER, "ABOGACÍA")]})

    def test_a_degree_carries_everything_the_sheet_states(self) -> None:
        refs = self._refs()
        dataset = build_dataset(refs, {refs[0].url: SHEET})
        career = dataset["datos"]["carreras"][0]
        self.assertEqual(career["universidad_nombre"], UNIVERSITY)
        self.assertEqual(career["titulo_otorgado"], "Abogado")
        self.assertEqual(career["duracion_anios"], 4.0)
        self.assertEqual(career["cantidad_materias_total"], 42)
        self.assertTrue(career["tiene_titulo_intermedio"])
        self.assertEqual(dataset["datos"]["ofertas"][0]["coneau_resolucion"], "Nº 459/20")
        validate_dataset(dataset)

    def test_the_sheet_decides_the_level_over_the_list(self) -> None:
        refs = discover_programmes({GRADO_INDEX: [(CAREER, "ABOGACÍA")]})
        sheet = SHEET.replace("<td>Grado</td>", "<td>Posgrado</td>")
        dataset = build_dataset(refs, {refs[0].url: sheet})
        self.assertEqual(dataset["datos"]["carreras"], [])
        self.assertEqual(len(dataset["datos"]["posgrados"]), 1)

    def test_a_service_page_is_excluded_with_its_reason(self) -> None:
        refs = self._refs()
        dataset = build_dataset(refs, {refs[0].url: "<p>Consultorio contable</p>"})
        self.assertEqual(dataset["datos"]["carreras"], [])
        self.assertIn("no publica datos",
                      dataset["control_calidad"]["programas_excluidos"][0]["motivo"])

    def test_a_page_that_did_not_download_is_excluded_with_its_reason(self) -> None:
        dataset = build_dataset(self._refs(), {})
        self.assertIn("no se pudo descargar",
                      dataset["control_calidad"]["programas_excluidos"][0]["motivo"])
