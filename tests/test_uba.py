"""Tests for the Universidad de Buenos Aires adapter."""

import unittest

from rumbo_scraper.parsers.uba import (
    BASE_URL, CABA, UNIVERSITY, build_dataset, discover_faculties, faculty_name,
    parse_address, parse_authorities, parse_campuses, parse_careers, parse_links,
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
