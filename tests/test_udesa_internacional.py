"""Tests for the remaining UdeSA sections."""

import unittest

from rumbo_scraper.parsers.udesa import (
    UNIVERSITY, derive_activities, parse_international_programmes, parse_social_channels,
)


class InternationalTests(unittest.TestCase):
    URL = "https://udesa.edu.ar/programas-de-doble-diploma"

    def test_the_type_and_level_come_from_the_page(self) -> None:
        pages = {self.URL: {"sections": [
            {"label": "Yale University", "body": "<p>Disponible para el MBA.</p>"}]}}
        row = parse_international_programmes(pages)[0]
        self.assertEqual(row["nombre_programa"], "Yale University")
        self.assertEqual(row["tipo_programa"], "Doble diploma")
        self.assertIsNone(row["nivel"])
        self.assertEqual(row["requisitos"], "Disponible para el MBA.")
        self.assertEqual(row["universidad_nombre"], UNIVERSITY)

    def test_the_exchange_pages_carry_their_level(self) -> None:
        pages = {"https://udesa.edu.ar/intercambio-de-grado": {"sections": [
            {"label": "Postulación", "body": "<p>Desde tercer año.</p>"}]}}
        self.assertEqual(parse_international_programmes(pages)[0]["nivel"], "Grado")

    def test_unpublished_columns_stay_null(self) -> None:
        pages = {self.URL: {"sections": [{"label": "Yale", "body": "<p>x</p>"}]}}
        row = parse_international_programmes(pages)[0]
        for field in ("cantidad_convenios", "duracion_maxima",
                      "reconocimiento_academico", "arancel_destino_cubierto"):
            self.assertIsNone(row[field], field)

    def test_a_page_that_did_not_load_is_skipped(self) -> None:
        self.assertEqual(parse_international_programmes({}), [])


class SocialChannelTests(unittest.TestCase):
    def test_reads_the_institutional_profiles(self) -> None:
        html = ('<a href="https://www.instagram.com/udesa.edu.ar">i</a>'
                '<a href="https://www.linkedin.com/school/universidad-de-san-andres">l</a>')
        rows = parse_social_channels(html, "https://udesa.edu.ar")
        self.assertEqual([row["canal"] for row in rows], ["Instagram", "LinkedIn"])
        self.assertEqual(rows[0]["usuario_o_direccion"], "https://instagram.com/udesa.edu.ar")

    def test_a_tracking_endpoint_is_not_a_profile(self) -> None:
        html = '<img src="https://www.facebook.com/tr?id=123&ev=PageView">'
        self.assertEqual(parse_social_channels(html, "https://udesa.edu.ar"), [])

    def test_a_share_link_is_not_a_profile(self) -> None:
        html = '<a href="https://twitter.com/intent/tweet?url=x">t</a>'
        self.assertEqual(parse_social_channels(html, "https://udesa.edu.ar"), [])

    def test_x_and_twitter_are_the_same_channel(self) -> None:
        rows = parse_social_channels('<a href="https://x.com/UdeSA">x</a>', "https://udesa.edu.ar")
        self.assertEqual(rows[0]["canal"], "Twitter")

    def test_the_same_profile_linked_twice_is_stored_once(self) -> None:
        html = '<a href="https://x.com/UdeSA">a</a><a href="https://x.com/UdeSA">b</a>'
        self.assertEqual(len(parse_social_channels(html, "https://udesa.edu.ar")), 1)

    def test_an_unrendered_page_yields_nothing(self) -> None:
        self.assertEqual(parse_social_channels("", "https://udesa.edu.ar"), [])


class ActivityTests(unittest.TestCase):
    def _subjects(self, *names: str) -> list[dict]:
        return [{"nombre_materia": name, "carrera_o_programa": "Abogacía"} for name in names]

    def test_recognises_the_published_activity_kinds(self) -> None:
        rows = derive_activities(self._subjects(
            "Taller de Escritura", "Práctica Profesional Supervisada",
            "Seminario de Investigación", "Trabajo Final Integrador",
            "Pasantía en la industria", "Intercambio académico"))
        self.assertEqual({row["tipo_actividad"] for row in rows},
                         {"Taller", "Práctica Profesional", "Seminario",
                          "Trabajo Final / Tesis", "Pasantía", "Intercambio"})

    def test_the_thesis_wins_over_the_workshop_as_in_the_utdt_adapter(self) -> None:
        row = derive_activities(self._subjects("Taller de Tesis"))[0]
        self.assertEqual(row["tipo_actividad"], "Trabajo Final / Tesis")

    def test_an_ordinary_subject_is_not_an_activity(self) -> None:
        self.assertEqual(derive_activities(self._subjects("Microeconomía Avanzada")), [])

    def test_keeps_the_published_name_and_its_parent(self) -> None:
        row = derive_activities(self._subjects("Taller de Escritura"))[0]
        self.assertEqual(row["nombre_actividad"], "Taller de Escritura")
        self.assertEqual(row["carrera_o_programa"], "Abogacía")
        self.assertIsNone(row["obligatoria"])
        self.assertIsNone(row["carga_horaria_total"])
