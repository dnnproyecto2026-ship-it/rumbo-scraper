"""Tests for the UADE adapter."""

import unittest

from rumbo_scraper.parsers.uade import (
    BASE_URL, PLAN_SUFFIX, UNIVERSITY, build_dataset, classify, discover_programmes,
    duration_years, faculty_name, modality, page_title, parse_facts, parse_study_plan,
    sitemap_paths,
)
from rumbo_scraper.validators.uade import validate_dataset

CAREER = "/facultad-de-arquitectura-y-urbanismo/arquitectura"


class DiscoveryTests(unittest.TestCase):
    """A programme is the page that has a study plan beside it."""

    def test_only_a_page_with_a_plan_is_a_programme(self) -> None:
        paths = [CAREER, CAREER + PLAN_SUFFIX,
                 "/facultad-de-arquitectura-y-urbanismo/novedades"]
        refs, _ = discover_programmes(paths, {CAREER: "Arquitectura"})
        self.assertEqual([r.name for r in refs], ["Arquitectura"])
        self.assertEqual(refs[0].url, f"{BASE_URL}{CAREER}")
        self.assertEqual(refs[0].faculty, "Facultad de Arquitectura y Urbanismo")

    def test_a_page_outside_a_faculty_is_not_a_programme(self) -> None:
        paths = ["/acerca-de-uade/algo", "/acerca-de-uade/algo" + PLAN_SUFFIX]
        self.assertEqual(discover_programmes(paths, {"/acerca-de-uade/algo": "X"})[0], ())

    def test_a_page_without_a_title_is_excluded_with_its_reason(self) -> None:
        refs, excluded = discover_programmes([CAREER, CAREER + PLAN_SUFFIX], {})
        self.assertEqual(refs, ())
        self.assertIn("no publica un título", excluded[0]["motivo"])

    def test_a_name_that_declares_no_kind_is_excluded(self) -> None:
        refs, excluded = discover_programmes(
            [CAREER, CAREER + PLAN_SUFFIX], {CAREER: "Economía Empresarial"})
        self.assertEqual(refs, ())
        self.assertIn("no declara el tipo", excluded[0]["motivo"])

    def test_reads_the_locations_of_the_sitemap(self) -> None:
        xml = (f"<urlset><url><loc>{BASE_URL}{CAREER}/</loc></url>"
               f"<url><loc>{BASE_URL}/</loc></url></urlset>")
        self.assertEqual(sitemap_paths(xml), ["", CAREER])


class ClassifyTests(unittest.TestCase):
    def test_the_word_that_opens_the_name_decides(self) -> None:
        # A combined programme names both; the first word is the one that counts.
        self.assertEqual(classify("Lic. en Administración de Empresas + MBA"),
                         ("Grado", None))
        self.assertEqual(classify("MBA + Lic. en Administración"), ("Posgrado", "Maestría"))

    def test_recognises_every_kind_the_university_publishes(self) -> None:
        self.assertEqual(classify("Tecnicatura en Periodismo"), ("Pregrado", None))
        self.assertEqual(classify("Diplomatura en Gestión"), ("Posgrado", "Diplomatura"))
        self.assertEqual(classify("Doble Titulación en Economía"), ("Grado", None))
        self.assertEqual(classify("Arquitectura"), ("Grado", None))

    def test_a_name_without_a_marker_is_left_unclassified(self) -> None:
        self.assertEqual(classify("Cocinero Profesional"), (None, None))

    def test_turns_the_slug_into_the_published_name(self) -> None:
        self.assertEqual(faculty_name("facultad-de-ciencias-de-la-salud"),
                         "Facultad de Ciencias de la Salud")


class FactTests(unittest.TestCase):
    def test_reads_the_length_and_the_intermediate_degree(self) -> None:
        html = ("<p>Arquitectura Duración: 5 años Título intermedio a los 3 años "
                "Técnico Universitario en Documentación Quiero inscribirme</p>")
        facts = parse_facts(html)
        self.assertEqual(facts["duracion"], "5 años")
        self.assertIn("Técnico Universitario", facts["titulo_intermedio"])

    def test_the_modality_is_the_word_after_its_label(self) -> None:
        html = "<p>Modalidad blended : cursá hasta un 30% en modalidad virtual</p>"
        self.assertEqual(parse_facts(html)["modalidad"], "blended")

    def test_blended_is_the_mixed_modality(self) -> None:
        self.assertEqual(modality("blended"), "Híbrida")
        self.assertEqual(modality("Online"), "Virtual")
        self.assertEqual(modality("Presencial"), "Presencial")

    def test_converts_the_published_length(self) -> None:
        self.assertEqual(duration_years("5 años"), 5.0)
        self.assertIsNone(duration_years("a confirmar"))

    def test_the_name_is_the_first_heading(self) -> None:
        self.assertEqual(page_title("<h1>Arquitectura</h1><h1>Otro</h1>"), "Arquitectura")
        self.assertIsNone(page_title("<p>sin título</p>"))


class StudyPlanTests(unittest.TestCase):
    HTML = ("<p>Primer Año</p><ul><li>ARQUITECTURA chevron_right</li>"
            "<li>FÍSICA APLICADA chevron_right</li></ul>"
            "<p>Segundo Año</p><ul><li>URBANISMO chevron_right</li></ul>"
            "<p>Estudiar en UADE</p><ul><li>Sistema de Ingreso</li></ul>")

    def test_reads_the_subjects_of_each_year_without_the_icon(self) -> None:
        rows = parse_study_plan(self.HTML, "Arquitectura")
        self.assertEqual([r["nombre_materia"] for r in rows],
                         ["ARQUITECTURA", "FÍSICA APLICADA", "URBANISMO"])
        self.assertEqual([r["anio_cursada"] for r in rows], [1, 1, 2])

    def test_a_list_that_no_year_introduces_is_not_the_plan(self) -> None:
        rows = parse_study_plan(self.HTML, "Arquitectura")
        self.assertNotIn("Sistema de Ingreso", [r["nombre_materia"] for r in rows])

    def test_a_page_without_a_plan_yields_nothing(self) -> None:
        self.assertEqual(parse_study_plan("<p>Sin plan</p>", "X"), [])


class BuildTests(unittest.TestCase):
    def _refs(self, title: str = "Arquitectura"):
        return discover_programmes([CAREER, CAREER + PLAN_SUFFIX], {CAREER: title})

    def test_a_degree_carries_what_the_pages_publish(self) -> None:
        refs, excluded = self._refs()
        pages = {refs[0].url: "<p>Duración: 5 años Modalidad blended : cursá</p>"}
        plans = {refs[0].url + PLAN_SUFFIX: StudyPlanTests.HTML}
        dataset = build_dataset(refs, pages, plans, excluded)
        career = dataset["datos"]["carreras"][0]
        self.assertEqual(career["universidad_nombre"], UNIVERSITY)
        self.assertEqual(career["duracion_anios"], 5.0)
        self.assertEqual(career["cantidad_materias_total"], 3)
        self.assertEqual(dataset["datos"]["ofertas"][0]["modalidad"], "Híbrida")
        validate_dataset(dataset)

    def test_the_awarded_degree_is_never_asserted(self) -> None:
        # UADE states whether an intermediate degree exists, not its own title.
        refs, excluded = self._refs()
        dataset = build_dataset(refs, {refs[0].url: "<p>Duración: 5 años</p>"},
                                {}, excluded)
        self.assertIsNone(dataset["datos"]["carreras"][0]["titulo_otorgado"])

    def test_a_page_that_did_not_download_is_excluded_with_its_reason(self) -> None:
        refs, excluded = self._refs()
        dataset = build_dataset(refs, {}, {}, excluded)
        failed = [r for r in dataset["control_calidad"]["programas_excluidos"]
                  if "no se pudo" in r["motivo"]]
        self.assertEqual(len(failed), 1)


class TituloPartidoTest(unittest.TestCase):
    def test_a_name_set_over_two_headings_is_read_whole(self):
        from rumbo_scraper.parsers.uade import page_title
        html = ('<h1><strong>Licenciatura en Ciencias de la </strong></h1><h1>Comunicación</h1>'
                '<h1>¿Por qué estudiar Ciencias de la Comunicación en UADE?</h1>')
        self.assertEqual(page_title(html), "Licenciatura en Ciencias de la Comunicación")
        self.assertEqual(page_title("<h1>Abogacía</h1><h1>¿Por qué?</h1>"), "Abogacía")
