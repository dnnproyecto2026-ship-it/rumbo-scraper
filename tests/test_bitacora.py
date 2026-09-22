"""Tests for the coverage log."""

import json
import tempfile
import unittest
from pathlib import Path

from rumbo_scraper import bitacora
from rumbo_scraper.contracts import SECTION_FIELDS


def _artifact(**sections) -> dict:
    data = {name: [] for name in SECTION_FIELDS}
    data.update(sections)
    return {
        "extraido_en": "2026-09-22T00:00:00+00:00",
        "metodo": "HTML público; sin IA",
        "datos": data,
        "directorio_academico": {"personas": [{"nombre_completo": "Ana"}],
                                 "roles_academicos": []},
        "control_calidad": {
            "secciones_sin_fuente_publica": {"aranceles": "no hay arancel publicado"},
            "materias_sin_anio": {"motivo": "los planes son cuadros"},
            "programas_excluidos": [{"nombre": "Curso", "motivo": "es un curso"}],
            "programas_unificados": [{"nombre": "X", "urls": ["a", "b"]}],
            "errores_descarga": [],
        },
    }


class CollectTests(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.dir = Path(self.folder.name)
        (self.dir / "utdt_completo.json").write_text(
            json.dumps(_artifact(carreras=[{"titulo_otorgado": "Abogado/a",
                                            "duracion_anios": 5,
                                            "cantidad_materias_total": None}])),
            encoding="utf-8")
        (self.dir / "utdt_pendientes.json").write_text(
            json.dumps({"total_pendientes": 7,
                        "resumen": {"alta": 1, "media": 2, "baja": 4}}),
            encoding="utf-8")

    def test_reads_the_artifact_and_its_audit(self) -> None:
        rows = bitacora.collect(self.dir)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["conteos"]["carreras"], 1)
        self.assertEqual(rows[0]["pendientes"], 7)
        self.assertEqual(rows[0]["personas"], 1)

    def test_counts_how_many_rows_carry_each_key_field(self) -> None:
        coverage = bitacora.collect(self.dir)[0]["campos"]
        self.assertEqual(coverage["carreras.titulo_otorgado"], (1, 1))
        self.assertEqual(coverage["carreras.cantidad_materias_total"], (0, 1))

    def test_a_university_without_an_artifact_is_skipped(self) -> None:
        self.assertEqual(len(bitacora.collect(Path(self.folder.name) / "vacio")), 0)

    def test_an_unreadable_artifact_does_not_break_the_log(self) -> None:
        (self.dir / "udesa_completo.json").write_text("{roto", encoding="utf-8")
        self.assertEqual(len(bitacora.collect(self.dir)), 1)


class RenderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.dir = Path(self.folder.name)
        (self.dir / "utdt_completo.json").write_text(
            json.dumps(_artifact(carreras=[{"titulo_otorgado": None}])), encoding="utf-8")

    def test_an_empty_section_states_the_reason_the_adapter_declared(self) -> None:
        text = bitacora.render(bitacora.collect(self.dir))
        self.assertIn("`aranceles` — no hay arancel publicado", text)

    def test_an_empty_section_without_a_reason_says_so(self) -> None:
        text = bitacora.render(bitacora.collect(self.dir))
        self.assertIn("`posgrados` — sin datos, causa no declarada", text)

    def test_reports_what_was_left_out_and_why(self) -> None:
        text = bitacora.render(bitacora.collect(self.dir))
        self.assertIn("1 programa(s) fuera del contrato: es un curso", text)
        self.assertIn("1 programa(s) publicados más de una vez", text)
        self.assertIn("los planes son cuadros", text)

    def test_the_log_is_markdown_with_a_summary_table(self) -> None:
        text = bitacora.render(bitacora.collect(self.dir))
        self.assertTrue(text.startswith("# Bitácora"))
        self.assertIn("| Universidad | Carreras |", text)
