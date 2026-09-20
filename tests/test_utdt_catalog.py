"""Tests for UTDT course catalogue parsing and preview."""

import unittest

from rumbo_scraper.database.load_utdt_catalog import _subject_name_key, preview
from rumbo_scraper.parsers.utdt_catalog import (
    parse_detail_row,
    parse_schedule_row,
    split_teachers,
)


class UTDTCatalogTests(unittest.TestCase):
    def test_parses_schedule_with_parentheses_in_name(self) -> None:
        row = parse_schedule_row([
            "Imagen y Artificio (IA) (5993)", "1", "Teórica-Práctica",
            "Guerrini, Tomás, Marcos, Manuel Henán", "Viernes", "15:30 - 17:05",
        ])
        self.assertEqual(row["codigo_materia"], "5993")
        self.assertEqual(row["nombre_materia"], "Imagen y Artificio (IA)")
        self.assertEqual(row["docentes"], ["Guerrini, Tomás", "Marcos, Manuel Henán"])
        self.assertEqual(row["hora_inicio"], "15:30")

    def test_parses_detail_code_and_section(self) -> None:
        row = parse_detail_row([
            "Tecnología Digital V: Diseño de Algoritmos (3813 - S1)",
            "Algoritmos avanzados", "Examen final", "",
        ], "https://example.edu/programa.pdf")
        self.assertEqual(row["codigo_materia"], "3813")
        self.assertEqual(row["seccion"], "1")
        self.assertEqual(row["programa_url"], "https://example.edu/programa.pdf")

    def test_teacher_split_falls_back_when_format_is_ambiguous(self) -> None:
        self.assertEqual(split_teachers("Equipo docente"), [])
        self.assertEqual(split_teachers("A designar, Agüero, Santiago"), ["Agüero, Santiago"])

    def test_preview_deduplicates_schedules(self) -> None:
        dataset = {
            "periodo": {"anio": 2026, "semestre": 2},
            "horarios": [{
                "codigo_materia": "1302", "nombre_materia": "Administración I",
                "seccion": "1", "tipo_clase": "Teórica", "docentes": ["Fabbri, Jessica"],
                "dia": "Lunes", "hora_inicio": "11:30", "hora_fin": "13:05",
            }],
            "detalles": [{
                "codigo_materia": "1302", "nombre_materia": "Administración I",
                "seccion": "1", "contenido": "Contenido", "condiciones_aprobacion": None,
                "programa_url": None,
            }],
        }
        counts = preview(dataset)
        self.assertEqual(counts["materias_catalogo"], 1)
        self.assertEqual(counts["comisiones_materia"], 1)
        self.assertEqual(counts["horarios_comision"], 1)
        self.assertEqual(counts["docentes"], 1)

    def test_plan_asterisks_do_not_prevent_exact_matching(self) -> None:
        self.assertEqual(
            _subject_name_key("Introducción a la Ciencia Política **"),
            _subject_name_key("Introducción a la Ciencia Política"),
        )
        self.assertNotEqual(_subject_name_key("Derecho I"), _subject_name_key("Derecho II"))


if __name__ == "__main__":
    unittest.main()
