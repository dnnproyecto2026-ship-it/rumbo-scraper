"""Tests for the UdeSA faculty directory and authorities."""

import unittest

from rumbo_scraper.parsers.udesa import UNIVERSITY, parse_authorities, parse_faculty_directory

UNITS = {
    "departamento de economia": f"{UNIVERSITY} — Departamento de Economía",
    "economia": f"{UNIVERSITY} — Departamento de Economía",
    "escuela de negocios": f"{UNIVERSITY} — Escuela de Negocios",
}
PROGRAMMES = {"maestria en economia": f"{UNIVERSITY} — Departamento de Economía"}
SOURCE = "https://udesa.edu.ar/cuerpo-docente"


def _professor(name: str, tags: list[str], url: str = "/cuerpo-docente/x") -> dict:
    return {"name": name, "url": url,
            "professorPicture": {"src": "https://images.udesa.edu.ar/x.jpg"},
            "tags": [{"name": tag} for tag in tags]}


class FacultyDirectoryTests(unittest.TestCase):
    def _parse(self, items: list[dict]):
        return parse_faculty_directory({"professors": {"items": items}}, SOURCE, UNITS, PROGRAMMES)

    def test_reads_the_person_with_an_absolute_profile_and_photo(self) -> None:
        people, _ = self._parse([_professor("Ana Pérez", ["Departamento de Economía"])])
        self.assertEqual(people[0]["nombre_completo"], "Ana Pérez")
        self.assertEqual(people[0]["perfil_url"], "https://udesa.edu.ar/cuerpo-docente/x")
        self.assertEqual(people[0]["foto_url"], "https://images.udesa.edu.ar/x.jpg")
        self.assertEqual(people[0]["fuente_url"], SOURCE)

    def test_a_programme_tag_becomes_a_role_in_that_programme(self) -> None:
        _, roles = self._parse([_professor("Ana Pérez", ["Maestría en Economía"])])
        self.assertEqual(roles[0]["carrera_nombre"], "Maestría en Economía")
        self.assertEqual(roles[0]["facultad_nombre"], UNITS["departamento de economia"])
        self.assertEqual(roles[0]["cargo"], "Profesor/a")
        self.assertFalse(roles[0]["es_autoridad"])

    def test_a_unit_tag_alone_becomes_a_faculty_role(self) -> None:
        _, roles = self._parse([_professor("Ana Pérez", ["Escuela de Negocios"])])
        self.assertEqual(roles[0]["facultad_nombre"], UNITS["escuela de negocios"])
        self.assertIsNone(roles[0]["carrera_nombre"])

    def test_an_untagged_professor_still_gets_a_role(self) -> None:
        _, roles = self._parse([_professor("Ana Pérez", [])])
        self.assertEqual(len(roles), 1)
        self.assertIsNone(roles[0]["facultad_nombre"])

    def test_the_same_person_is_listed_once(self) -> None:
        people, _ = self._parse([_professor("Ana Pérez", []), _professor("ANA PEREZ", [])])
        self.assertEqual(len(people), 1)

    def test_an_empty_directory_yields_nothing(self) -> None:
        self.assertEqual(self._parse([]), ([], []))


class AuthorityTests(unittest.TestCase):
    def _page(self, sections: list[dict]) -> dict:
        return {"https://udesa.edu.ar/autoridades": {"sections": sections}}

    def test_reads_a_module_whose_label_is_name_and_position(self) -> None:
        pages = self._page([{"label": "Lucas S. Grosman, Rector",
                             "body": "<p>Es Abogado y Doctor en Derecho.</p>"}])
        authorities, people, roles = parse_authorities(pages, UNITS)
        self.assertEqual(authorities[0]["nombre_autoridad"], "Lucas S. Grosman")
        self.assertEqual(authorities[0]["cargo"], "Rector")
        self.assertEqual(people[0]["biografia"], "Es Abogado y Doctor en Derecho.")
        self.assertTrue(roles[0]["es_autoridad"])

    def test_a_directors_group_takes_its_position_from_the_group(self) -> None:
        pages = self._page([{"label": "Directores",
                             "persons": [{"name": "Ana Pérez", "body": "<strong>Escuela de Negocios</strong>"}]}])
        authorities, _, _ = parse_authorities(pages, UNITS)
        self.assertEqual(authorities[0]["cargo"], "Director/a")
        self.assertEqual(authorities[0]["facultad_nombre"], UNITS["escuela de negocios"])

    def test_reads_the_unit_named_inside_the_position(self) -> None:
        pages = self._page([{"label": "Consejeros",
                             "persons": [{"name": "Ana Pérez",
                                          "body": "Directora del Departamento de Economía"}]}])
        authorities, _, _ = parse_authorities(pages, UNITS)
        self.assertEqual(authorities[0]["facultad_nombre"], UNITS["departamento de economia"])

    def test_strips_the_label_of_the_link_that_follows_the_position(self) -> None:
        pages = self._page([{"label": "Consejeros",
                             "persons": [{"name": "Ana Pérez", "body": "Vicerrectora Ver perfil"}]}])
        authorities, _, _ = parse_authorities(pages, UNITS)
        self.assertEqual(authorities[0]["cargo"], "Vicerrectora")

    def test_the_same_position_published_twice_is_stored_once(self) -> None:
        section = {"label": "Consejeros", "persons": [{"name": "Ana Pérez", "body": "Vicerrectora"}]}
        pages = {"https://udesa.edu.ar/a": {"sections": [section]},
                 "https://udesa.edu.ar/b": {"sections": [section]}}
        authorities, people, _ = parse_authorities(pages, UNITS)
        self.assertEqual(len(authorities), 1)
        self.assertEqual(len(people), 1)

    def test_a_person_with_two_positions_is_one_person_and_two_authorities(self) -> None:
        pages = self._page([
            {"label": "Consejeros", "persons": [{"name": "Ana Pérez", "body": "Vicerrectora"}]},
            {"label": "Directores", "persons": [{"name": "Ana Pérez", "body": "Escuela de Negocios"}]},
        ])
        authorities, people, _ = parse_authorities(pages, UNITS)
        self.assertEqual(len(authorities), 2)
        self.assertEqual(len(people), 1)

    def test_an_unknown_unit_leaves_the_faculty_null_instead_of_guessing(self) -> None:
        pages = self._page([{"label": "Directores",
                             "persons": [{"name": "Ana Pérez", "body": "Departamento de Ingeniería"}]}])
        authorities, _, _ = parse_authorities(pages, UNITS)
        self.assertEqual(authorities[0]["cargo"], "Director/a")
        self.assertIsNone(authorities[0]["facultad_nombre"])
