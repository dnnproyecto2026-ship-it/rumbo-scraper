"""Tests for the Universidad de Buenos Aires adapter."""

import unittest

from rumbo_scraper.parsers.uba import (
    BASE_URL, CABA, UNIVERSITY, build_dataset, discover_faculties, faculty_name,
    POSTGRADUATE_SOURCES, POSTGRADUATES_NOT_READ, STRATEGIES, build_postgraduates,
    chrome_lines, parse_address, parse_authorities, parse_campuses, parse_careers,
    parse_links, read_postgraduates,
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

    def test_the_faculties_that_are_not_read_are_declared(self) -> None:
        # One of the thirteen publishes its offer in a form this reader does
        # not cover, and silence would look the same as an empty catalogue.
        self.assertEqual(len(POSTGRADUATES_NOT_READ), 1)
        self.assertTrue(all(reason for reason in POSTGRADUATES_NOT_READ.values()))
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
