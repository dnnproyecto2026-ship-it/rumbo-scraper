"""Tests for the ITBA adapter."""

import unittest

from rumbo_scraper.parsers.itba import (
    UNIVERSITY, build_dataset, discover_programmes, duration_months, duration_years,
    expand_programme_name, parse_attendance, parse_authorities, parse_campuses,
    parse_labelled_prose, parse_study_plan, parse_teacher_page, programme_level,
    sitemap_urls,
)
from rumbo_scraper.validators.itba import validate_dataset


def _strip(cells: str) -> str:
    """The theme renders each cell as a column of two paragraphs."""
    columns = "".join(
        f'<div class="et_pb_column"><div><p>{label}</p></div>'
        f'<div><p>{value}</p></div></div>'
        for label, value in (pair.split("=", 1) for pair in cells.split(";"))
    )
    return f'<html><body><div class="et_pb_row">{columns}</div></body></html>'


class NameTests(unittest.TestCase):
    def test_expands_the_abbreviation_where_it_stands(self) -> None:
        self.assertEqual(expand_programme_name("Ing. Civil")[0], "Ingeniería Civil")
        self.assertEqual(expand_programme_name("Ing. en Petróleo")[0], "Ingeniería en Petróleo")
        self.assertEqual(expand_programme_name("Mtr. en Fintech")[0], "Maestría en Fintech")

    def test_keeps_both_degrees_of_a_combined_programme(self) -> None:
        name, kind = expand_programme_name("Mtr. y Esp. en Ciencia de Datos")
        self.assertEqual(name, "Maestría y Especialización en Ciencia de Datos")
        self.assertEqual(kind, "Maestría")

    def test_a_label_without_an_abbreviation_is_kept_as_published(self) -> None:
        self.assertEqual(expand_programme_name("Bioingeniería"), ("Bioingeniería", None))

    def test_the_level_comes_from_the_abbreviation_or_the_section(self) -> None:
        self.assertEqual(programme_level("Ing. Civil"), "Grado")
        self.assertEqual(programme_level("Mtr. en Fintech"), "Posgrado")
        self.assertEqual(programme_level("Bioingeniería", "grado"), "Grado")
        self.assertIsNone(programme_level("Bioingeniería"))


class DiscoveryTests(unittest.TestCase):
    def test_reads_the_programmes_the_menu_links(self) -> None:
        refs = discover_programmes([
            ("/grado/ingenieria-civil/", "Ing. Civil"),
            ("/posgrado/maestria-en-fintech/", "Mtr. en Fintech"),
        ])
        self.assertEqual([ref.name for ref in refs],
                         ["Ingeniería Civil", "Maestría en Fintech"])
        self.assertEqual(refs[0].url, "https://www.itba.edu.ar/grado/ingenieria-civil/")

    def test_ignores_a_link_outside_a_programme_path(self) -> None:
        self.assertEqual(discover_programmes([("/la-universidad/", "Ing. Civil")]), ())

    def test_ignores_a_level_that_contradicts_the_section(self) -> None:
        self.assertEqual(discover_programmes([("/grado/x/", "Mtr. en Fintech")]), ())

    def test_the_same_programme_linked_twice_is_listed_once(self) -> None:
        refs = discover_programmes([("/grado/ingenieria-civil/", "Ing. Civil"),
                                    ("/grado/ingenieria-civil", "Ing. Civil")])
        self.assertEqual(len(refs), 1)


class AttendanceTests(unittest.TestCase):
    STRIP = "Duración=5 años;Modalidad=Presencial;Sede=Multisede;Dedicación=Full-time"

    def test_pairs_each_label_with_its_published_value(self) -> None:
        self.assertEqual(parse_attendance(_strip(self.STRIP)), {
            "duracion": "5 años", "modalidad": "Presencial",
            "sede": "Multisede", "dedicacion": "Full-time"})

    def test_reads_the_strip_that_states_the_length_not_another_one(self) -> None:
        html = (_strip("Modalidad=Semipresencial").replace("</body>", "")
                + _strip(self.STRIP).split("<body>")[1])
        self.assertEqual(parse_attendance(html)["modalidad"], "Presencial")

    def test_falls_back_to_the_prose_a_postgraduate_writes(self) -> None:
        html = "<html><body><p>Inicio: mayo 2027 Duración: 2 años Modalidad: virtual</p></body></html>"
        values = parse_attendance(html)
        self.assertEqual(values["duracion"], "2 años")
        self.assertEqual(values["inicio"], "mayo 2027")

    def test_converts_the_published_length(self) -> None:
        self.assertEqual(duration_years("5 años"), 5.0)
        self.assertEqual(duration_months("2 años"), 24)
        self.assertEqual(duration_months("3 cuatrimestres"), 12)
        self.assertIsNone(duration_years("a definir"))


class DegreeTests(unittest.TestCase):
    def test_reads_the_awarded_degree_without_its_accreditation(self) -> None:
        html = ("<html><body><p>Título que otorga: Magíster en Gestión de Negocios "
                "y Analítica Acreditada en Sesión CONEAU N° 578</p></body></html>")
        self.assertEqual(parse_labelled_prose(html, "Título que otorga"),
                         "Magíster en Gestión de Negocios y Analítica")

    def test_stops_at_the_next_labelled_fact(self) -> None:
        html = "<html><body><p>Título que otorga: Magíster en Fintech Modalidad presencial</p></body></html>"
        self.assertEqual(parse_labelled_prose(html, "Título que otorga"), "Magíster en Fintech")


class StudyPlanTests(unittest.TestCase):
    HTML = """<html><body><div><p>1° año</p><p>Primer cuatrimestre</p>
      <ul><li>! Álgebra</li><li>! Análisis Matemático I</li></ul>
      <p>Segundo cuatrimestre</p><ul><li>! Física I</li></ul></div>
      <div><p>2° año</p><ul><li>! Química</li></ul></div></body></html>"""

    def test_reads_the_subjects_with_the_year_the_page_states(self) -> None:
        rows = parse_study_plan(self.HTML, "Ingeniería Civil")
        self.assertEqual([row["nombre_materia"] for row in rows],
                         ["Álgebra", "Análisis Matemático I", "Física I", "Química"])
        self.assertEqual([row["anio_cursada"] for row in rows], [1, 1, 1, 2])
        self.assertEqual({row["regimen"] for row in rows}, {"Cuatrimestral"})

    def test_a_page_without_a_plan_yields_nothing(self) -> None:
        self.assertEqual(parse_study_plan("<html><body><p>Sin plan</p></body></html>", "X"), [])


class CampusTests(unittest.TestCase):
    HTML = """<html><body><h3>Sede Distrito Financiero</h3>
      <p>San Martín 202 Ciudad Autónoma de Buenos Aires Ver en mapa</p>
      <h3>Nuevo Campus</h3><p>Futura y única sede</p></body></html>"""

    def test_splits_the_published_address(self) -> None:
        localities, campuses = parse_campuses(self.HTML)
        self.assertEqual(campuses[0]["calle"], "San Martín")
        self.assertEqual(campuses[0]["numero"], "202")
        self.assertEqual(localities[0]["provincia"], "CABA")

    def test_a_campus_without_an_address_keeps_it_null(self) -> None:
        _, campuses = parse_campuses(self.HTML)
        self.assertEqual(campuses[1]["nombre_sede"], "Nuevo Campus")
        self.assertIsNone(campuses[1]["calle"])


class AuthorityTests(unittest.TestCase):
    def test_only_a_name_marked_with_its_title_is_a_person(self) -> None:
        html = """<html><body><h3>Consejo Académico</h3>
          <h3>ING. SEBASTÍAN MUR</h3><p>RECTOR</p>
          <h3>Oferta Académica</h3></body></html>"""
        rows = parse_authorities(html)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["nombre_autoridad"], "Sebastían Mur")
        self.assertEqual(rows[0]["cargo"], "RECTOR")


class TeacherTests(unittest.TestCase):
    def test_reads_the_name_from_the_title_not_the_generic_heading(self) -> None:
        html = "<html><head><title>Cecilia Pedró | ITBA</title></head><body><h1>Docente</h1></body></html>"
        person = parse_teacher_page(html, "https://www.itba.edu.ar/docentes/cecilia-pedro/")
        self.assertEqual(person["nombre_completo"], "Cecilia Pedró")
        self.assertEqual(person["perfil_url"], "https://www.itba.edu.ar/docentes/cecilia-pedro/")

    def test_a_page_without_a_name_is_skipped(self) -> None:
        self.assertIsNone(parse_teacher_page("<html><head><title>Docente</title></head></html>", "x"))


class BuildTests(unittest.TestCase):
    def _refs(self):
        return discover_programmes([("/grado/ingenieria-civil/", "Ing. Civil")])

    def test_a_section_page_is_excluded_for_want_of_the_full_strip(self) -> None:
        refs = discover_programmes([("/grado/ingreso/", "Ingreso")])
        dataset = build_dataset(refs, {refs[0].url: _strip("Duración=16 semanas")})
        self.assertEqual(dataset["datos"]["carreras"], [])
        self.assertEqual(len(dataset["control_calidad"]["programas_excluidos"]), 1)

    def test_a_degree_with_the_full_strip_is_loaded(self) -> None:
        refs = self._refs()
        dataset = build_dataset(refs, {refs[0].url: _strip(
            "Duración=5 años;Modalidad=Presencial;Sede=Multisede")})
        career = dataset["datos"]["carreras"][0]
        self.assertEqual(career["nombre_carrera"], "Ingeniería Civil")
        self.assertEqual(career["duracion_anios"], 5.0)
        self.assertEqual(dataset["datos"]["ofertas"][0]["sede"], "Multisede")
        validate_dataset(dataset)

    def test_a_programme_that_did_not_download_is_excluded_with_its_reason(self) -> None:
        dataset = build_dataset(self._refs(), {})
        self.assertIn("no se pudo descargar",
                      dataset["control_calidad"]["programas_excluidos"][0]["motivo"])

    def test_validation_refuses_a_run_where_every_degree_failed(self) -> None:
        # Losing them all is a broken run, not a university without degrees.
        with self.assertRaises(ValueError):
            validate_dataset(build_dataset(self._refs(), {}))

    def test_the_same_person_published_twice_is_stored_once(self) -> None:
        pages = {f"https://www.itba.edu.ar/docentes/{slug}/":
                 "<html><head><title>Ana Pérez | ITBA</title></head></html>"
                 for slug in ("ana-perez", "ana-perez-2")}
        dataset = build_dataset((), {}, teacher_pages=pages)
        self.assertEqual(len(dataset["directorio_academico"]["personas"]), 1)


class SitemapTests(unittest.TestCase):
    def test_reads_every_location(self) -> None:
        xml = "<urlset><url><loc>https://a/</loc></url><url><loc>https://b/</loc></url></urlset>"
        self.assertEqual(sitemap_urls(xml), ["https://a/", "https://b/"])


class PlanPdfTests(unittest.TestCase):
    """The plan documents name each year in capitals and list subjects under it."""

    def test_reads_the_years_and_the_subjects_under_them(self) -> None:
        from rumbo_scraper.parsers.itba import _PDF_SECTION, _PDF_TRAILER, _PDF_YEAR
        self.assertTrue(_PDF_YEAR.match("PRIMER AÑO"))
        self.assertTrue(_PDF_YEAR.match("QUINTO AÑO"))
        self.assertIsNone(_PDF_YEAR.match("Química General"))

    def test_an_elective_heading_clears_the_year(self) -> None:
        from rumbo_scraper.parsers.itba import _PDF_SECTION
        for heading in ("Electivas", "Optativas", "Minors", "Orientaciones"):
            self.assertTrue(_PDF_SECTION.match(heading), heading)
        self.assertIsNone(_PDF_SECTION.match("Electrónica Digital"))

    def test_the_closing_block_ends_the_plan(self) -> None:
        from rumbo_scraper.parsers.itba import _PDF_TRAILER
        for line in ("// INFO DE CONTACTO", "DURACIÓN TOTAL DE LA CARRERA: 5 AÑOS",
                     "TÍTULO QUE SE EXPIDE: INGENIERO/A CIVIL",
                     "Resolución de acreditación CONEAU"):
            self.assertTrue(_PDF_TRAILER.search(line), line)
        self.assertIsNone(_PDF_TRAILER.search("Mecánica de Fluidos"))

    def test_layout_leftovers_are_not_subjects(self) -> None:
        from rumbo_scraper.parsers.itba import _PDF_NOISE
        for line in ("//////////", "-----", "Primer cuatrimestre Segundo cuatrimestre"):
            self.assertTrue(_PDF_NOISE.match(line), line)
        self.assertIsNone(_PDF_NOISE.match("Análisis Matemático I"))

    def test_an_unreadable_document_yields_nothing(self) -> None:
        from rumbo_scraper.parsers.itba import parse_plan_pdf, parse_plan_pdf_degree
        self.assertEqual(parse_plan_pdf(b"no es un pdf", "X"), [])
        self.assertIsNone(parse_plan_pdf_degree(b""))
