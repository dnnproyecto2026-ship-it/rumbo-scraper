"""Tests for the complete UTDT scraper contract."""

import unittest

from rumbo_scraper.contracts import SECTION_FIELDS
from rumbo_scraper.parsers.utdt import (
    ACADEMIC_UNITS, CAREERS, build_dataset, parse_career_detail,
    parse_careers, parse_study_plan,
)
from rumbo_scraper.validators.utdt import validate_dataset


class UTDTParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.admissions = "<html><h2>marzo 2027</h2>" + "".join(
            f"<a>{key}</a>" for key in CAREERS
        ) + "</html>"
        self.institution = "<html>" + " ".join(
            f"{unit_type} de {name}" for name, unit_type in ACADEMIC_UNITS
        ) + " Maestría en Economía Doctorado en Historia</html>"

    def test_contract_contains_every_excel_section(self) -> None:
        self.assertEqual(len(SECTION_FIELDS), 15)
        self.assertIn("aranceles", SECTION_FIELDS)
        self.assertIn("posgrados", SECTION_FIELDS)
        self.assertIn("redes_contacto", SECTION_FIELDS)

    def test_extracts_current_careers(self) -> None:
        careers = parse_careers(self.admissions)
        self.assertEqual(len(careers), 13)
        self.assertEqual(len({item.denominacion_canonica for item in careers}), 13)

    def test_parses_detail_and_study_plan(self) -> None:
        config = CAREERS["abogacia"]
        detail_html = """
        <html><meta name="description" content="Una descripción suficientemente extensa para presentar la carrera de Abogacía y explicar claramente su propuesta académica.">
        <h4>Duración</h4><h5>5 años</h5><h4>Modalidad</h4><h5>100% presencial</h5>
        <h4>Lugar</h4><h5>Campus Di Tella</h5><a href="/plan">Ver plan de estudios</a>
        <a>María Ejemplo</a><p>Directora de la carrera</p><p>Pasantías y Di Tella Gateway</p></html>
        """
        detail = parse_career_detail(detail_html, config)
        self.assertEqual(detail["duracion_anios"], 5.0)
        self.assertEqual(detail["modalidad"], "Presencial")
        self.assertEqual(detail["plan_url"], "https://www.utdt.edu/plan")
        plan = parse_study_plan(
            "<p>Título: Abogado</p><p>Duración: 5 años</p><h3>1</h3><h4>1.º semestre</h4><ul><li>Derecho Constitucional I</li></ul>",
            "Abogacía",
        )
        self.assertEqual(plan["titulo_otorgado"], "Abogado")
        self.assertEqual(len(plan["materias"]), 1)

    def test_builds_and_validates_all_sections(self) -> None:
        detail_pages = {
            config.detail_url: "<h4>Duración</h4><h5>4 años</h5><h4>Modalidad</h4><h5>Presencial</h5>"
            for config in CAREERS.values()
        }
        dataset = build_dataset(self.admissions, self.institution, detail_pages, {})
        validate_dataset(dataset)
        self.assertEqual(set(dataset["datos"]), set(SECTION_FIELDS))
        self.assertEqual(len(dataset["datos"]["carreras"]), 13)
        self.assertIn("turnos_anio", dataset["control_calidad"]["secciones_vacias"])


if __name__ == "__main__":
    unittest.main()
