"""Tests for the UCA adapter."""

import unittest

from rumbo_scraper.parsers.uca import (
    BASE_URL, UNIVERSITY, build_dataset, classify, discover_faculties,
    discover_programmes, duration_months, duration_years, faculty_name, modality,
    parse_facts, parse_study_plan,
)
from rumbo_scraper.validators.uca import validate_dataset

FACULTY = f"{BASE_URL}/es/facultades/facultad-de-derecho"


class FacultyTests(unittest.TestCase):
    def test_reads_the_faculties_the_hub_links(self) -> None:
        links = [(f"{BASE_URL}/es/facultades/facultad-de-derecho", "Derecho"),
                 (f"{BASE_URL}/es/facultades/facultad-de-derecho/carrera-de-grado/x", "X"),
                 (f"{BASE_URL}/es/institucional", "Institucional")]
        self.assertEqual(discover_faculties(links), (FACULTY,))

    def test_turns_the_slug_into_the_published_name(self) -> None:
        self.assertEqual(faculty_name("facultad-de-ciencias-sociales"),
                         "Facultad de Ciencias Sociales")


class ClassifyTests(unittest.TestCase):
    def test_the_section_states_the_level(self) -> None:
        self.assertEqual(classify("Abogacía", "carrera-de-grado"), ("Grado", None))
        self.assertEqual(classify("X", "maestria"), ("Posgrado", "Maestría"))

    def test_the_name_states_it_when_the_section_does_not(self) -> None:
        self.assertEqual(classify("Licenciatura en Economía", "x"), ("Grado", None))
        self.assertEqual(classify("Doctorado en Derecho", "x"), ("Posgrado", "Doctorado"))

    def test_the_kind_is_found_after_the_subject_too(self) -> None:
        # UCA writes "Inglés - Profesorado" as well as "Profesorado en Inglés".
        self.assertEqual(classify("Inglés - Profesorado", "x"), ("Grado", None))
        self.assertEqual(classify("Psicopedagogía - Licenciatura (Ciclo)", "x"),
                         ("Grado", None))

    def test_a_tecnicatura_is_a_pregrado(self) -> None:
        self.assertEqual(classify("Tecnicatura en Marketing", "x"), ("Pregrado", None))

    def test_a_name_that_declares_nothing_is_left_unclassified(self) -> None:
        self.assertEqual(classify("Bibliotecología (modalidad a distancia)", "x"),
                         (None, None))


class DiscoveryTests(unittest.TestCase):
    def test_reads_the_programmes_a_faculty_links(self) -> None:
        pages = {FACULTY: [
            (f"{FACULTY}/carrera-de-grado/abogacia", "Abogacía"),
            (f"{BASE_URL}/es/facultades/otra/carrera-de-grado/x", "X"),
        ]}
        refs, _ = discover_programmes(pages)
        self.assertEqual([r.name for r in refs], ["Abogacía"])
        self.assertEqual(refs[0].faculty, "Facultad de Derecho")

    def test_an_unclassifiable_link_is_excluded_with_its_reason(self) -> None:
        pages = {FACULTY: [(f"{FACULTY}/otra-seccion/bibliotecologia", "Bibliotecología")]}
        refs, excluded = discover_programmes(pages)
        self.assertEqual(refs, ())
        self.assertIn("nivel", excluded[0]["motivo"])


class FactTests(unittest.TestCase):
    def test_reads_the_facts_the_page_publishes_in_capitals(self) -> None:
        html = "<p>TÍTULO: Arquitecto/a DURACIÓN: 5 años + Plan de estudio + Materias</p>"
        self.assertEqual(parse_facts(html),
                         {"titulo": "Arquitecto/a", "duracion": "5 años"})

    def test_the_last_fact_is_read_even_without_a_label_after_it(self) -> None:
        # Without the "+" marker as a terminator the length was never read.
        html = "<p>TÍTULO: Abogado/a DURACIÓN: 5 años + Observaciones</p>"
        self.assertEqual(parse_facts(html)["duracion"], "5 años")

    def test_converts_the_published_length(self) -> None:
        self.assertEqual(duration_years("5 años"), 5.0)
        self.assertEqual(duration_months("18 meses"), 18)
        self.assertIsNone(duration_years("a confirmar"))

    def test_maps_the_modality(self) -> None:
        self.assertEqual(modality("Presencial"), "Presencial")
        self.assertEqual(modality("A distancia"), "Virtual")
        self.assertIsNone(modality(None))


class StudyPlanTests(unittest.TestCase):
    HTML = ("<div><p><strong>PRIMER AÑO</strong></p>"
            "<p>1° semestre<br>Introducción al Derecho<br>Filosofía</p>"
            "<p><strong>SEGUNDO AÑO</strong></p>"
            "<p>1° semestre<br>Derecho Penal</p></div>")

    def test_splits_the_subjects_a_paragraph_joins_with_line_breaks(self) -> None:
        rows = parse_study_plan(self.HTML, "Abogacía")
        self.assertEqual([r["nombre_materia"] for r in rows],
                         ["Introducción al Derecho", "Filosofía", "Derecho Penal"])
        self.assertEqual([r["anio_cursada"] for r in rows], [1, 1, 2])
        self.assertEqual({r["regimen"] for r in rows}, {"Semestral"})

    def test_the_degrees_and_requirements_are_not_subjects(self) -> None:
        html = ("<div><p><strong>PRIMER AÑO</strong></p>"
                "<p>TÍTULO INTERMEDIO: Procurador<br>Requisito: inglés<br>Derecho Civil</p></div>")
        rows = parse_study_plan(html, "Abogacía")
        self.assertEqual([r["nombre_materia"] for r in rows], ["Derecho Civil"])

    def test_a_page_without_a_plan_yields_nothing(self) -> None:
        self.assertEqual(parse_study_plan("<p>Sin plan</p>", "X"), [])


class BuildTests(unittest.TestCase):
    def _refs(self, *links):
        return discover_programmes({FACULTY: list(links)})

    def test_a_degree_carries_what_the_page_publishes(self) -> None:
        refs, excluded = self._refs((f"{FACULTY}/carrera-de-grado/abogacia", "Abogacía"))
        html = "<p>TÍTULO: Abogado/a DURACIÓN: 5 años + x</p>" + StudyPlanTests.HTML
        dataset = build_dataset(refs, {refs[0].url: html}, excluded)
        career = dataset["datos"]["carreras"][0]
        self.assertEqual(career["universidad_nombre"], UNIVERSITY)
        self.assertEqual(career["titulo_otorgado"], "Abogado/a")
        self.assertEqual(career["duracion_anios"], 5.0)
        self.assertEqual(career["nivel"], "Grado")
        validate_dataset(dataset)

    def test_a_tecnicatura_is_a_career_with_its_level(self) -> None:
        refs, excluded = self._refs(
            (f"{FACULTY}/carrera/tecnicatura-en-marketing", "Tecnicatura en Marketing"))
        dataset = build_dataset(refs, {refs[0].url: "<p>x</p>"}, excluded)
        self.assertEqual(dataset["datos"]["carreras"][0]["nivel"], "Pregrado")

    def test_a_page_that_did_not_render_is_excluded_with_its_reason(self) -> None:
        refs, excluded = self._refs(
            (f"{FACULTY}/carrera-de-grado/abogacia", "Abogacía"),
            (f"{FACULTY}/carrera-de-grado/notariado", "Notariado"))
        dataset = build_dataset(refs, {refs[0].url: "<p>x</p>"}, excluded)
        failed = [r for r in dataset["control_calidad"]["programas_excluidos"]
                  if "renderizar" in r["motivo"]]
        self.assertEqual(len(failed), 1)
        validate_dataset(dataset)
