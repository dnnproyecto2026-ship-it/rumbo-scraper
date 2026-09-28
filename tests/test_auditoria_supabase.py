"""Tests for the read-only audit of what Supabase holds."""

import unittest

from rumbo_scraper.database import auditoria_supabase as auditoria


def _tablas(**overrides):
    tablas = {tabla: [] for tabla in auditoria.TABLAS}
    tablas.update({
        "universidades": [
            {"id": "u1", "nombre_oficial": "Universidad de Buenos Aires",
             "nombre_corto": "UBA", "tipo_gestion": "Estatal"},
            {"id": "u2", "nombre_oficial": "Universidad Torcuato Di Tella",
             "nombre_corto": "UTDT", "tipo_gestion": "Privada"},
        ],
        "facultades": [{"id": "f1", "universidad_id": "u2"}],
        "carreras": [
            # Complete: title, duration, plan and an offer at a campus.
            {"id": "c1", "universidad_id": "u2", "titulo_otorgado": "Abogado/a",
             "duracion_anios": 5, "facultad_id": "f1"},
            # No title and no plan.
            {"id": "c2", "universidad_id": "u1", "titulo_otorgado": None,
             "duracion_anios": 6},
            # Nothing at all.
            {"id": "c3", "universidad_id": "u1", "titulo_otorgado": "",
             "duracion_anios": None},
        ],
        "ofertas_academicas": [
            {"id": "o1", "carrera_id": "c1", "sede_id": "s1"},
            {"id": "o2", "carrera_id": "c2", "sede_id": "s2"},
            {"id": "o3", "carrera_id": "c3", "sede_id": None},
        ],
        "materias": [{"id": "m1", "universidad_id": "u2", "carrera_id": "c1",
                      "anio_cursada": 1}],
        "aranceles": [{"id": "a1", "oferta_id": "o1"}],
        "autoridades": [{"id": "x1", "facultad_id": "f1"}],
    })
    tablas.update(overrides)
    return tablas


def _uni(informe, corto):
    return next(u for u in informe["universidades"] if u["corto"] == corto)


class AuditarTests(unittest.TestCase):
    def test_a_career_is_comparable_only_with_title_duration_plan_and_campus(self) -> None:
        informe = auditoria.auditar(_tablas())
        self.assertEqual(_uni(informe, "UTDT")["carreras_comparables"], 1)
        self.assertEqual(_uni(informe, "UBA")["carreras_comparables"], 0)

    def test_counts_what_each_career_is_missing(self) -> None:
        sin = _uni(auditoria.auditar(_tablas()), "UBA")["carreras_sin"]
        self.assertEqual(sin, {"título": 2, "duración": 1, "plan": 2, "sede": 1})

    def test_rows_reach_their_university_through_the_row_they_point_at(self) -> None:
        informe = auditoria.auditar(_tablas())
        utdt = _uni(informe, "UTDT")
        self.assertEqual(utdt["ofertas_con_arancel"], 1)
        self.assertEqual(utdt["conteos"]["autoridades"], 1)
        self.assertEqual(utdt["conteos"]["ofertas_academicas"], 1)
        self.assertEqual(_uni(informe, "UBA")["conteos"]["ofertas_academicas"], 2)

    def test_the_biggest_gap_comes_first(self) -> None:
        informe = auditoria.auditar(_tablas())
        self.assertEqual(informe["universidades"][0]["corto"], "UBA")

    def test_field_coverage_is_rows_with_the_field_over_rows(self) -> None:
        campos = _uni(auditoria.auditar(_tablas()), "UBA")["campos"]
        self.assertEqual(campos["carreras.titulo_otorgado"], (0, 2))
        self.assertEqual(campos["carreras.duracion_anios"], (1, 2))

    def test_an_unreadable_table_is_reported_not_counted_as_empty(self) -> None:
        informe = auditoria.auditar(_tablas(aranceles=None))
        self.assertIn("aranceles", informe["tablas_no_leidas"])
        self.assertNotIn("aranceles", informe["tablas_vacias"])

    def test_names_catalogue_universities_missing_from_the_database(self) -> None:
        informe = auditoria.auditar(_tablas())
        self.assertIn("Universidad Nacional de las Artes", informe["fuera_de_la_base"])
        self.assertNotIn("Universidad de Buenos Aires", informe["fuera_de_la_base"])


class RenderTests(unittest.TestCase):
    def test_the_report_is_markdown_with_the_comparable_table(self) -> None:
        text = auditoria.render(auditoria.auditar(_tablas()))
        self.assertTrue(text.startswith("# Auditoría de Supabase"))
        self.assertIn("| UBA | Estatal | 2 | 0 (0%) | 2 | 1 | 2 | 1 |", text)
        self.assertIn("Carreras: 3; comparables: 1 (33%)", text)


if __name__ == "__main__":
    unittest.main()
