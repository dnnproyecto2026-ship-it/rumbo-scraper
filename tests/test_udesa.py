"""Tests for deterministic UdeSA Next.js parsers."""

import unittest

from rumbo_scraper.parsers.udesa import (
    CAREERS, build_dataset, discover_plan_url, parse_career_detail,
    parse_campuses, parse_study_plan,
)
from rumbo_scraper.validators.udesa import validate_dataset


class UdeSAParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = CAREERS[0]
        self.career_page = {
            "title": "Abogacía",
            "attendance": [
                {"label": "Duración", "body": "5 años"},
                {"label": "Sede", "body": "Campus Victoria"},
                {"label": "Modalidad", "body": "Presencial"},
            ],
            "header": {"description": "<p>Formación jurídica rigurosa.</p>", "src": "https://images.udesa.edu.ar/a.jpg"},
            "navigationCards": [{"undergraduatePage": [{
                "undergraduatePageType": "Plan de estudios", "url": "/abogacia/plan-de-estudios"
            }]}],
        }
        self.plan_page = {
            "undergraduateSyllabus": {
                "references": [{"name": "Ciclo jurídico", "color": "ABC123"}],
                "table": [{"lateralHeading": "1° Semestre", "subTable": [{
                    "1° año": {"value": "Derecho Constitucional", "color": "ABC123"},
                    "2° año": {"value": "", "color": ""},
                }]}],
            },
            "undergraduateSections": [{"attachments3": [{
                "src": "https://images.udesa.edu.ar/plan.pdf",
                "documentDescription": "Plan en PDF",
            }]}],
        }

    def test_parses_structured_career_fields(self) -> None:
        row = parse_career_detail(self.config, self.career_page, "https://udesa.edu.ar/abogacia")
        self.assertEqual(row["duration_years"], 5.0)
        self.assertEqual(row["modality"], "Presencial")
        self.assertEqual(row["description"], "Formación jurídica rigurosa.")
        self.assertEqual(discover_plan_url(self.career_page, row["url"]), "https://udesa.edu.ar/abogacia/plan-de-estudios")

    def test_parses_syllabus_and_documents(self) -> None:
        subjects, resources = parse_study_plan(
            self.plan_page, "Abogacía", "https://udesa.edu.ar/abogacia/plan-de-estudios"
        )
        self.assertEqual(len(subjects), 1)
        self.assertEqual(subjects[0]["nombre_materia"], "Derecho Constitucional")
        self.assertEqual(subjects[0]["anio_cursada"], 1)
        self.assertEqual(subjects[0]["area_tematica"], "Ciclo jurídico")
        self.assertEqual(resources[0]["tipo_recurso"], "documento")

    def test_builds_complete_contract(self) -> None:
        career_pages = {}
        plan_pages = {}
        for config in CAREERS:
            url = "https://udesa.edu.ar" + config.url
            page = {**self.career_page, "title": config.name, "navigationCards": []}
            career_pages[url] = (page, url)
        dataset = build_dataset({}, career_pages, plan_pages)
        validate_dataset(dataset)
        self.assertEqual(len(dataset["datos"]["carreras"]), 18)
        self.assertEqual(dataset["metodo"], "Playwright + JSON estructurado de Next.js; sin IA")

    def test_parses_official_campus_addresses(self) -> None:
        html = """
        <section><h2>Campus Victoria</h2><p>Dirección: Vito Dumas 284
        (B1644BID) Victoria, Pcia. de Bs. As. Tel: (54-11) 7078-0400</p></section>
        <section><h2>Sede Callao</h2><p>Dirección: Av. Callao 1055
        (C1023AAD) CABA Tel: (54-11) 7078-0400</p></section>
        """
        localities, campuses = parse_campuses(html)
        self.assertEqual(len(localities), 2)
        self.assertEqual(campuses[0]["calle"], "Vito Dumas")
        self.assertEqual(campuses[1]["nombre_sede"], "Sede Callao")


if __name__ == "__main__":
    unittest.main()
