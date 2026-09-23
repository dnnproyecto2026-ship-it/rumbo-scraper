"""Tests for the Universidad de Buenos Aires adapter."""

import unittest

from rumbo_scraper.parsers.uba import (
    BASE_URL, CABA, UNIVERSITY, build_dataset, discover_faculties, faculty_name,
    POSTGRADUATE_SOURCES, POSTGRADUATES_NOT_READ, STRATEGIES, build_postgraduates,
    chrome_lines, parse_address, parse_authorities, parse_campuses, parse_careers,
    clean_subject, parse_links, plan_document_url, plan_is_sound,
    read_plan_tables, read_postgraduates,
)
from rumbo_scraper.validators.uba import validate_dataset

INDEX = """
<a href="/carreras/7" alt="Facultad de Derecho"><h2>Derecho</h2></a>
<a href="/carreras/5" alt="Faculta de Ciencias Sociales"><h2>Ciencias Sociales</h2></a>
<a href="/becas-grado" alt="Becas">Becas</a>
"""

# The careers are published with a self-closing anchor, so the name that
# survives the parse is the one in the alt attribute.
DERECHO = """
<div class="titulo"><h1>Derecho</h1></div>
<div class="datos-redes">
  <p><p>Av. Figueroa Alcorta 2263, Ciudad Autónoma de Buenos Aires - Argentina
  <br/>(+54 11) 5287-2000</p></p>
  <a href="http://www.derecho.uba.ar"></a>
  <a href="mailto:info@derecho.uba.ar"></a>
</div>
<ul class="lista-simple">
  <li><a href="http://www.derecho.uba.ar/abogacia" alt="Abogacía" class=""/>Abogacía</a></li>
  <li><a href="https://share.google/abc" alt="Traductorado Público" class=""/>x</a></li>
</ul>
"""

SOCIALES = """
<div class="titulo"><h1>Ciencias Sociales</h1></div>
<div class="datos-redes">
  <p><p>Sede SE <br/>Santiago del Estero 1029 - Ciudad Autónoma de Buenos Aires - Argentina
  <br/>(+54 11) 5287-1500 </p><p> Sede MT <br/>Marcelo T. de Alvear 2230 -
  Ciudad Autónoma de Buenos Aires - Argentina <br/>(+54 11) 5287-1500 </p></p>
  <a href="http://www.sociales.uba.ar"></a><a href="mailto:"></a>
</div>
<ul class="lista-simple">
  <li><a href="https://sociologia.sociales.uba.ar/" alt="Sociología" class=""/>x</a></li>
</ul>
"""

AUTHORITIES = """
<div class="b-azul"><h1>RECTOR</h1></div>
<h1 class="f-azul">Ricardo Jorge Gelpi</h1>
<h2 class="accordion-header">SECRETARÍA GENERAL</h2>
<h2 class="f-azul">Secretario General</h2>
<h2 class="f-naranja sub">Juan Alfonsín</h2>
<h3 class="f-azul">Subsecretario de Asuntos Jurídicos</h3>
<h3 class="f-naranja sub">Nicolás Aguerre</h3>
"""


class DiscoveryTests(unittest.TestCase):
    def test_reads_the_faculties_the_index_links(self) -> None:
        refs = discover_faculties(INDEX)
        self.assertEqual([ref.name for ref in refs],
                         ["Facultad de Derecho", "Faculta de Ciencias Sociales"])
        self.assertEqual(refs[0].url, f"{BASE_URL}/carreras/7")

    def test_a_link_that_is_not_a_faculty_is_ignored(self) -> None:
        self.assertEqual(len(discover_faculties(INDEX)), 2)

    def test_the_long_form_of_the_index_wins_over_the_page_heading(self) -> None:
        self.assertEqual(faculty_name(DERECHO, "Facultad de Derecho"),
                         "Facultad de Derecho")

    def test_a_page_with_no_heading_keeps_the_name_of_the_index(self) -> None:
        self.assertEqual(faculty_name("<p>x</p>", "Facultad de Derecho"),
                         "Facultad de Derecho")


class AddressTests(unittest.TestCase):
    def test_splits_street_number_and_postal_code(self) -> None:
        self.assertEqual(
            parse_address(["Av. San Martín 4453 - C1417DSE - "
                           "Ciudad Autónoma de Buenos Aires - Argentina"]),
            {"calle": "Av. San Martín", "numero": "4453", "codigo_postal": "C1417DSE"},
        )

    def test_what_follows_the_number_belongs_to_the_street(self) -> None:
        # The building and the campus are part of the address, not of the
        # number, so they stay with the street instead of being dropped.
        address = parse_address(["Intendente Güiraldes 2160, Pabellón III, "
                                 "Ciudad Universitaria (C1428EGA) - "
                                 "Ciudad Autónoma de Buenos Aires"])
        self.assertEqual(address["numero"], "2160")
        self.assertEqual(address["calle"],
                         "Intendente Güiraldes, Pabellón III, Ciudad Universitaria")

    def test_reads_the_old_four_digit_postal_code(self) -> None:
        address = parse_address(["Puan 480, C1420 Ciudad Autónoma de Buenos Aires"])
        self.assertEqual(address["calle"], "Puan")
        self.assertEqual(address["codigo_postal"], "C1420")

    def test_an_empty_block_yields_nulls_and_not_a_crash(self) -> None:
        self.assertEqual(parse_address([]),
                         {"calle": None, "numero": None, "codigo_postal": None})


class FacultyPageTests(unittest.TestCase):
    def test_a_faculty_with_one_address_names_its_campus_after_itself(self) -> None:
        campuses = parse_campuses(DERECHO, "Facultad de Derecho")
        self.assertEqual([c.name for c in campuses], ["Facultad de Derecho"])
        self.assertEqual(campuses[0].phone, "(+54 11) 5287-2000")

    def test_a_faculty_with_two_buildings_reads_both_with_their_names(self) -> None:
        campuses = parse_campuses(SOCIALES, "Facultad de Ciencias Sociales")
        self.assertEqual([c.name for c in campuses], ["Sede SE", "Sede MT"])
        self.assertEqual([c.street for c in campuses],
                         ["Santiago del Estero", "Marcelo T. de Alvear"])

    def test_the_career_name_comes_from_the_attribute_the_parse_survives(self) -> None:
        self.assertEqual([name for name, _ in parse_careers(DERECHO)],
                         ["Abogacía", "Traductorado Público"])

    def test_an_empty_mail_link_is_not_a_contact(self) -> None:
        self.assertEqual(parse_links(SOCIALES),
                         {"sitio": "http://www.sociales.uba.ar"})
        self.assertEqual(parse_links(DERECHO)["email"], "info@derecho.uba.ar")


class AuthorityTests(unittest.TestCase):
    def test_reads_both_shapes_the_page_writes(self) -> None:
        rows = parse_authorities(AUTHORITIES)
        self.assertEqual([(r["cargo"], r["nombre_autoridad"]) for r in rows], [
            ("RECTOR", "Ricardo Jorge Gelpi"),
            ("Secretario General", "Juan Alfonsín"),
            ("Subsecretario de Asuntos Jurídicos", "Nicolás Aguerre"),
        ])

    def test_they_belong_to_the_university_and_not_to_a_faculty(self) -> None:
        self.assertTrue(all(row["facultad_nombre"] is None
                            for row in parse_authorities(AUTHORITIES)))


class DatasetTests(unittest.TestCase):
    def _dataset(self) -> dict:
        refs = discover_faculties(INDEX)
        return build_dataset(refs, {refs[0].url: DERECHO, refs[1].url: SOCIALES},
                             AUTHORITIES)

    def test_every_career_becomes_a_row_and_an_offer(self) -> None:
        data = self._dataset()["datos"]
        self.assertEqual([row["nombre_carrera"] for row in data["carreras"]],
                         ["Abogacía", "Traductorado Público", "Sociología"])
        self.assertEqual(len(data["ofertas"]), 3)
        self.assertEqual(data["carreras"][0]["nivel"], "Grado")
        self.assertEqual(data["localidades"][0]["nombre_localidad"], CABA)

    def test_a_career_of_a_faculty_with_one_campus_is_offered_there(self) -> None:
        offers = self._dataset()["datos"]["ofertas"]
        self.assertEqual(offers[0]["sede"], "Facultad de Derecho")

    def test_a_career_of_a_faculty_with_two_campuses_has_none(self) -> None:
        # The catalogue does not say which building teaches it.
        dataset = self._dataset()
        self.assertIsNone(dataset["datos"]["ofertas"][2]["sede"])
        self.assertEqual(dataset["control_calidad"]["carreras_sin_sede_publicada"], 1)

    def test_the_evidence_of_an_offer_is_the_page_that_published_it(self) -> None:
        # One faculty links a career through a URL shortener, which is not an
        # address of the university, so it cannot be the evidence field.
        dataset = self._dataset()
        self.assertEqual(dataset["datos"]["ofertas"][1]["url_oficial"],
                         f"{BASE_URL}/carreras/7")
        shortened = [r for r in dataset["recursos_publicos"]
                     if r["entidad_nombre"] == "Traductorado Público"]
        self.assertFalse(shortened[0]["en_dominio_oficial"])

    def test_the_faculty_written_out_of_form_is_reported(self) -> None:
        quality = self._dataset()["control_calidad"]
        self.assertEqual(quality["nombres_de_facultad_fuera_de_forma"],
                         ["Faculta de Ciencias Sociales"])

    def test_what_the_central_catalogue_does_not_publish_is_declared(self) -> None:
        quality = self._dataset()["control_calidad"]
        declared = quality["secciones_sin_fuente_publica"]
        self.assertIn("materias", declared)
        self.assertIn("carreras.duracion_anios", declared)
        self.assertIn("materias", quality["secciones_vacias"])

    def test_the_dataset_respects_the_contract(self) -> None:
        dataset = self._dataset()
        self.assertEqual(dataset["universidad"], UNIVERSITY)
        validate_dataset(dataset)

    def test_a_faculty_that_did_not_download_is_excluded_with_its_reason(self) -> None:
        refs = discover_faculties(INDEX)
        dataset = build_dataset(refs, {refs[0].url: DERECHO}, AUTHORITIES)
        self.assertIn("no se pudo descargar",
                      dataset["control_calidad"]["facultades_excluidas"][0]["motivo"])
        validate_dataset(dataset)

    def test_an_offer_in_a_campus_that_was_never_listed_is_rejected(self) -> None:
        dataset = self._dataset()
        dataset["datos"]["ofertas"][0]["sede"] = "Sede Inventada"
        with self.assertRaises(ValueError):
            validate_dataset(dataset)


if __name__ == "__main__":
    unittest.main()


MAESTRIAS_LISTA = """
<h2>Maestrías</h2>
<ul>
  <li><a href="/p/1">Automatización Industrial</a></li>
  <li><a href="/p/2">Ciencias de la Ingeniería</a></li>
  <li><a href="/p/3">Maestría en Explotación de Datos</a></li>
  <li><a href="/p/4">Inscripción y requisitos</a></li>
</ul>
<h2>Otras Maestrías</h2>
"""

ESPECIALIZACIONES_TITULOS = """
<h3>Carrera de Especialización en Biotecnología</h3>
<p>Texto.</p>
<h3>Carrera de Especialización en Bromatología</h3>
<p>Texto.</p>
<h3>Especializaciones</h3>
"""

DIPLOMATURAS_PARRAFOS = """
<h2>Diplomaturas</h2>
<p>Requiere admisión previa antes de inscribirse.</p>
<p>Internet de las Cosas</p>
<p>Ciencia de Datos Aplicada</p>
<p>Contactarse con info@fi.uba.ar</p>
"""


class PostgraduateTests(unittest.TestCase):
    def test_a_list_lends_its_kind_to_the_bare_names(self) -> None:
        rows = read_postgraduates(MAESTRIAS_LISTA, "lista", "Maestría")
        self.assertEqual([row["nombre"] for row in rows], [
            "Maestría en Automatización Industrial",
            "Maestría en Ciencias de la Ingeniería",
            "Maestría en Explotación de Datos",
        ])
        self.assertTrue(all(row["tipo"] == "Maestría" for row in rows))

    def test_a_name_that_states_its_kind_keeps_it(self) -> None:
        # The faculty files it under one heading and the name says another; the
        # name is the one the university gave the programme.
        rows = read_postgraduates(
            '<h2>Carreras de Especialización</h2><ul>'
            '<li><a href="/a">Maestría en Biotecnología</a></li>'
            '<li><a href="/b">Especialización en Farmacia Clínica</a></li></ul>',
            "lista", "Especialización",
        )
        self.assertEqual([(r["tipo"], r["nombre"]) for r in rows], [
            ("Maestría", "Maestría en Biotecnología"),
            ("Especialización", "Especialización en Farmacia Clínica"),
        ])

    def test_a_page_where_each_programme_is_a_heading_is_read(self) -> None:
        rows = read_postgraduates(ESPECIALIZACIONES_TITULOS, "titulos",
                                  "Especialización")
        self.assertEqual([row["nombre"] for row in rows], [
            "Carrera de Especialización en Biotecnología",
            "Carrera de Especialización en Bromatología",
        ])

    def test_the_plural_of_a_kind_opens_a_section_and_is_not_a_programme(self) -> None:
        names = {row["nombre"] for row in
                 read_postgraduates(MAESTRIAS_LISTA, "lista", "Maestría")}
        self.assertNotIn("Maestría en Otras Maestrías", names)
        self.assertNotIn("Maestría en Inscripción y requisitos", names)

    def test_a_page_written_as_plain_text_uses_the_repeated_lines_as_furniture(self) -> None:
        chrome = chrome_lines({"a": DIPLOMATURAS_PARRAFOS, "b": DIPLOMATURAS_PARRAFOS})
        self.assertEqual(read_postgraduates(DIPLOMATURAS_PARRAFOS, "parrafos",
                                            "Diplomatura", chrome), [])
        rows = read_postgraduates(DIPLOMATURAS_PARRAFOS, "parrafos", "Diplomatura")
        self.assertEqual([row["nombre"] for row in rows], [
            "Diplomatura en Internet de las Cosas",
            "Diplomatura en Ciencia de Datos Aplicada",
        ])

    def test_an_unknown_strategy_is_an_error_and_not_an_empty_list(self) -> None:
        with self.assertRaises(ValueError):
            read_postgraduates(MAESTRIAS_LISTA, "adivinar", "Maestría")

    def test_an_index_that_publishes_nothing_is_reported(self) -> None:
        faculty, url, kind, _ = POSTGRADUATE_SOURCES[0]
        rows, _, empty = build_postgraduates({url: "<p>Nada</p>"})
        self.assertEqual(rows, [])
        self.assertEqual(empty[0]["motivo"], "el índice no publicó ningún programa")

    def test_every_source_declares_a_strategy_the_reader_knows(self) -> None:
        # Two strategies carry an argument after a colon: which tab to open
        # and which element of the markup holds the name.
        self.assertTrue(all(strategy.split(":", 1)[0] in STRATEGIES
                            for _, _, _, strategy in POSTGRADUATE_SOURCES))

    def test_every_faculty_of_the_university_has_a_source(self) -> None:
        # The thirteen are read; a faculty that stops being readable is
        # declared here, because silence looks the same as an empty catalogue.
        self.assertEqual(POSTGRADUATES_NOT_READ, {})
        self.assertEqual(len({faculty for faculty, _, _, _ in POSTGRADUATE_SOURCES}), 13)

    def test_a_faculty_is_never_both_read_and_declared_unreadable(self) -> None:
        read = {faculty for faculty, _, _, _ in POSTGRADUATE_SOURCES}
        self.assertFalse(read & set(POSTGRADUATES_NOT_READ))


MEZCLA = """
<h2>Carreras de especialización</h2>
<ul>
  <li>Maestría en Biotecnología</li>
  <li>Especialización en Bioquímica</li>
  <li>Doctorado y Posdoctorado</li>
  <li>Doctorado, área Farmacia y el Doctorado Binacional</li>
  <li>Comisión de Doctorado:</li>
  <li>Una noticia cualquiera sin tipo</li>
</ul>
"""

PANELES = """
<ul class="nav"><li><a href="#curso-1">MAESTRÍAS</a></li></ul>
<div id="curso-0"><ul><li><a href="/a">Diplomatura Superior en Patología Bucal</a></li></ul></div>
<div id="curso-1"><ul><li><a href="/b">Cirugía Bucal</a></li>
<li><a href="/c">Imagenología Bucal</a></li></ul></div>
"""

SELECTOR = """
<div class="carrera"><h3><a href="/m1">Derecho Administrativo</a></h3>
<p class="content"><strong>Director:</strong> Juan Pérez</p></div>
<div class="carrera"><h3><a href="/m2">Derecho Procesal Civil</a></h3>
<p class="content"><strong>Director:</strong> Ana Gómez</p></div>
"""

SECCIONES = """
<h3>Maestrías</h3><ul><li>Administración Pública</li></ul>
<h3>Diplomaturas de posgrado</h3><ul><li>Recursos Humanos</li></ul>
"""


class NameTests(unittest.TestCase):
    def test_a_person_joined_to_their_post_is_not_a_programme(self) -> None:
        page = ('<ul><li>Emanuel Porcelli | Subsecretario de Maestrías</li>'
                '<li>Maestría en Políticas Sociales</li></ul>')
        self.assertEqual(
            [row["nombre"] for row in read_postgraduates(page, "mezcla", "Maestría")],
            ["Maestría en Políticas Sociales"],
        )

    def test_a_name_written_as_the_tail_of_its_heading_is_not_doubled(self) -> None:
        # Medicina writes "en Biología Molecular Médica" under "Oferta de
        # Maestrías", so the kind completes the name instead of repeating it.
        page = '<div class="t">en Biología Molecular Médica</div>'
        self.assertEqual(
            read_postgraduates(page, "selector:div.t", "Maestría")[0]["nombre"],
            "Maestría en Biología Molecular Médica",
        )


class MixedPageTests(unittest.TestCase):
    def test_only_the_entries_that_name_their_kind_are_read(self) -> None:
        rows = read_postgraduates(MEZCLA, "mezcla", "Especialización")
        self.assertEqual([row["nombre"] for row in rows],
                         ["Maestría en Biotecnología", "Especialización en Bioquímica"])

    def test_a_line_that_names_two_programmes_is_a_sentence(self) -> None:
        names = {row["nombre"] for row in
                 read_postgraduates(MEZCLA, "mezcla", "Especialización")}
        self.assertNotIn("Doctorado y Posdoctorado", names)
        self.assertNotIn("Doctorado, área Farmacia y el Doctorado Binacional", names)

    def test_a_label_that_ends_in_a_colon_is_not_a_programme(self) -> None:
        names = {row["nombre"] for row in
                 read_postgraduates(MEZCLA, "mezcla", "Especialización")}
        self.assertNotIn("Comisión de Doctorado:", names)


class PanelTests(unittest.TestCase):
    def test_the_tab_the_source_names_decides_the_kind(self) -> None:
        rows = read_postgraduates(PANELES, "panel:curso-1", "Maestría")
        self.assertEqual([row["nombre"] for row in rows],
                         ["Maestría en Cirugía Bucal", "Maestría en Imagenología Bucal"])

    def test_a_tab_that_does_not_exist_yields_nothing(self) -> None:
        self.assertEqual(read_postgraduates(PANELES, "panel:curso-9", "Maestría"), [])


class SelectorTests(unittest.TestCase):
    def test_the_markup_separates_the_name_from_its_director(self) -> None:
        rows = read_postgraduates(SELECTOR, "selector:div.carrera h3", "Maestría")
        self.assertEqual([row["nombre"] for row in rows],
                         ["Maestría en Derecho Administrativo",
                          "Maestría en Derecho Procesal Civil"])


class SectionTests(unittest.TestCase):
    def test_a_page_with_one_section_per_kind_is_read_once_per_kind(self) -> None:
        # The same page holds the maestrías and the diplomaturas, so the
        # heading that opens the block has to be the one being asked for.
        maestrias = read_postgraduates(SECCIONES, "lista", "Maestría")
        diplomaturas = read_postgraduates(SECCIONES, "lista", "Diplomatura")
        self.assertEqual([r["nombre"] for r in maestrias],
                         ["Maestría en Administración Pública"])
        self.assertEqual([r["nombre"] for r in diplomaturas],
                         ["Diplomatura en Recursos Humanos"])

    def test_a_name_the_extractor_cut_in_half_is_not_a_programme(self) -> None:
        cut = '<h3>Maestrías</h3><ul><li>Maestría con título</li>'\
              '<li>Gestión Ambiental Metropolitana</li></ul>'
        self.assertEqual([r["nombre"] for r in read_postgraduates(cut, "lista", "Maestría")],
                         ["Maestría en Gestión Ambiental Metropolitana"])


CAREER_PAGE = """
<h1>Agronomía</h1>
<a href="/carreras/agronomia">Carrera</a>
<a href="/sites/default/files/plan-2017.pdf">Plan de estudios</a>
<a href="https://share.google/abc">Plan de estudios resumido</a>
"""


class PlanLinkTests(unittest.TestCase):
    def test_finds_the_plan_the_faculty_links(self) -> None:
        url = plan_document_url(CAREER_PAGE, "https://www.agro.uba.ar/carreras/agronomia")
        self.assertEqual(url, "https://www.agro.uba.ar/sites/default/files/plan-2017.pdf")

    def test_a_plan_hosted_outside_the_university_is_not_taken(self) -> None:
        page = '<a href="https://share.google/abc">Plan de estudios</a>'
        self.assertIsNone(plan_document_url(page, "https://www.agro.uba.ar/x"))

    def test_a_page_with_no_plan_yields_nothing(self) -> None:
        self.assertIsNone(plan_document_url("<a href='/x'>Ingreso</a>",
                                            "https://www.agro.uba.ar/x"))

    def test_the_code_the_table_prints_beside_a_name_is_not_part_of_it(self) -> None:
        self.assertEqual(clean_subject("cod86 Administración General"),
                         "Administración General")
        self.assertEqual(clean_subject("Química Analítica F"), "Química Analítica")

    def test_a_legend_of_the_table_is_not_a_subject(self) -> None:
        self.assertIsNone(clean_subject("Total 30 720"))
        self.assertIsNone(clean_subject("F Final TP Trabajos Prácticos Para cursar"))


class PlanReadingTests(unittest.TestCase):
    def test_a_reading_that_loses_the_year_is_rejected(self) -> None:
        subjects = [{"nombre_materia": f"Materia {i}", "anio_cursada": None}
                    for i in range(10)]
        sound, reason = plan_is_sound(subjects)
        self.assertFalse(sound)
        self.assertIn("año", reason)

    def test_a_reading_that_runs_subjects_together_is_rejected(self) -> None:
        subjects = [{"nombre_materia": "x" * 90, "anio_cursada": 1} for _ in range(10)]
        sound, reason = plan_is_sound(subjects)
        self.assertFalse(sound)
        self.assertIn("une varias materias", reason)

    def test_a_document_too_short_to_be_a_plan_is_rejected(self) -> None:
        sound, reason = plan_is_sound([{"nombre_materia": "Álgebra", "anio_cursada": 1}])
        self.assertFalse(sound)
        self.assertIn("menos materias", reason)

    def test_a_clean_reading_is_accepted(self) -> None:
        subjects = [{"nombre_materia": f"Materia {i}", "anio_cursada": 1 + i % 5}
                    for i in range(12)]
        self.assertEqual(plan_is_sound(subjects), (True, ""))


PLAN_TABLE = """
<h3>Primer año</h3>
<table>
 <tr><th>Cód.</th><th>Asignatura</th><th>Hs.</th><th>Correlativas</th></tr>
 <tr><td>201</td><td>Anatomía I</td><td>110</td><td>Materias del CBC</td></tr>
 <tr><td>203</td><td>Química Orgánica</td><td>70</td><td>Anatomía I; Física Biológica</td></tr>
 <tr><td>603</td><td>Elementos de Estadística</td><td>40</td><td>Tener aprobadas 14 materias</td></tr>
 <tr><td>206</td><td>Anatomía II</td><td>100</td><td>Anatomía I; Química Orgánica</td></tr>
 <tr><td>202</td><td>Física Biológica</td><td>80</td><td>Química Orgánica; Estadística</td></tr>
 <tr><td>205</td><td>Histología</td><td>120</td><td>Anatomía I; Física Biológica</td></tr>
 <tr><td>207</td><td>Microbiología</td><td>90</td><td>Histología; Química Orgánica</td></tr>
 <tr><td>208</td><td>Fisiología</td><td>100</td><td>Histología; Física Biológica</td></tr>
</table>
"""

CALENDAR = """
<table>
 <tr><th>D</th><th>L</th><th>M</th><th>M</th><th>J</th><th>V</th><th>S</th></tr>
 <tr><td></td><td></td><td>1</td><td>2</td><td>3</td><td>4</td><td>5</td></tr>
 <tr><td>6</td><td>7</td><td>8</td><td>9</td><td>10</td><td>11</td><td>12</td></tr>
 <tr><td>13</td><td>14</td><td>15</td><td>16</td><td>17</td><td>18</td><td>19</td></tr>
 <tr><td>20</td><td>21</td><td>22</td><td>23</td><td>24</td><td>25</td><td>26</td></tr>
 <tr><td>27</td><td>28</td><td>29</td><td>30</td><td></td><td></td><td></td></tr>
</table>
"""


class PlanTableTests(unittest.TestCase):
    def test_reads_the_column_that_holds_the_names(self) -> None:
        # The widest column of a plan lists what has to be approved first, so
        # the column is chosen by how its cells read, not by how long they are.
        rows = read_plan_tables(PLAN_TABLE, "Veterinaria")["materias"]
        self.assertEqual([row["nombre_materia"] for row in rows], [
            "Anatomía I", "Química Orgánica", "Elementos de Estadística",
            "Anatomía II", "Física Biológica", "Histología", "Microbiología",
            "Fisiología",
        ])

    def test_the_year_announced_above_the_table_reaches_its_subjects(self) -> None:
        rows = read_plan_tables(PLAN_TABLE, "Veterinaria")["materias"]
        self.assertTrue(all(row["anio_cursada"] == 1 for row in rows))

    def test_the_calendar_of_the_sidebar_is_not_a_plan(self) -> None:
        result = read_plan_tables(CALENDAR, "Veterinaria")
        self.assertEqual(result["materias"], [])
        self.assertIn("no publica el plan como tabla", result["motivo"])

    def test_a_page_with_no_table_says_so(self) -> None:
        result = read_plan_tables("<p>El plan está en la resolución.</p>", "X")
        self.assertEqual(result["materias"], [])
        self.assertIn("no publica el plan como tabla", result["motivo"])

    def test_the_name_of_a_column_is_not_a_subject(self) -> None:
        names = {row["nombre_materia"]
                 for row in read_plan_tables(PLAN_TABLE, "Veterinaria")["materias"]}
        self.assertNotIn("Asignatura", names)
        self.assertNotIn("Correlativas", names)

    def test_a_requirement_is_never_read_as_a_subject(self) -> None:
        names = {row["nombre_materia"]
                 for row in read_plan_tables(PLAN_TABLE, "Veterinaria")["materias"]}
        self.assertFalse(any(";" in name or name.startswith("Tener")
                             for name in names))
