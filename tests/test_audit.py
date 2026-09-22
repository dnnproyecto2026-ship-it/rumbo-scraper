"""Tests for the per-university completeness audit."""

import json
import tempfile
import unittest
from pathlib import Path

from rumbo_scraper.database import audit_completeness as audit


class _Query:
    def __init__(self, client: "_Client", table: str) -> None:
        self.client, self.table_name = client, table
        self.filters: dict[str, object] = {}

    def select(self, columns: str) -> "_Query":
        self.columns = columns
        return self

    def eq(self, column: str, value: object) -> "_Query":
        self.filters[column] = value
        return self

    def order(self, column: str) -> "_Query":
        return self

    def range(self, start: int, end: int) -> "_Query":
        self.start, self.end = start, end
        return self

    def execute(self) -> object:
        rows = [row for row in self.client.tables.get(self.table_name, [])
                if all(row.get(k) == v for k, v in self.filters.items())]
        start, end = getattr(self, "start", 0), getattr(self, "end", len(rows))
        return type("R", (), {"data": rows[start:end + 1]})()


class _Client:
    def __init__(self, tables: dict[str, list[dict]]) -> None:
        self.tables = tables

    def table(self, name: str) -> _Query:
        return _Query(self, name)


UNIVERSITIES = [{"id": "u1", "nombre_oficial": "Universidad Torcuato Di Tella"},
                {"id": "u2", "nombre_oficial": "Universidad Austral"}]


class ScopeTests(unittest.TestCase):
    """The audit of one university must not count another university's rows."""

    def setUp(self) -> None:
        self.client = _Client({
            "universidades": UNIVERSITIES,
            "carreras": [
                {"id": "c1", "universidad_id": "u1", "titulo_otorgado": None,
                 "tiene_titulo_intermedio": "no", "cantidad_materias_total": 5},
                {"id": "c2", "universidad_id": "u2", "titulo_otorgado": None,
                 "tiene_titulo_intermedio": "no", "cantidad_materias_total": 5},
            ],
        })

    def test_only_the_rows_of_the_audited_university_are_reported(self) -> None:
        report = audit.build_report(self.client, "Universidad Torcuato Di Tella")
        titles = [i for i in report["pendientes"] if i["campo"] == "titulo_otorgado"]
        self.assertEqual(len(titles), 1)
        self.assertEqual(titles[0]["entidad_id"], "c1")
        self.assertEqual(titles[0]["universidad_id"], "u1")

    def test_a_university_that_is_not_loaded_is_refused(self) -> None:
        with self.assertRaises(RuntimeError):
            audit.build_report(self.client, "Universidad Inexistente")

    def test_a_filled_field_is_not_reported(self) -> None:
        report = audit.build_report(self.client, "Universidad Torcuato Di Tella")
        self.assertEqual(
            [i for i in report["pendientes"] if i["campo"] == "cantidad_materias_total"], []
        )


class IndirectScopeTests(unittest.TestCase):
    def test_a_table_is_scoped_through_the_row_that_carries_the_key(self) -> None:
        client = _Client({
            "universidades": UNIVERSITIES,
            "carreras": [{"id": "c1", "universidad_id": "u1"},
                         {"id": "c2", "universidad_id": "u2"}],
            "ofertas_academicas": [
                {"id": "o1", "carrera_id": "c1", "url_oficial": None, "regimen_ingreso": None},
                {"id": "o2", "carrera_id": "c2", "url_oficial": None, "regimen_ingreso": None},
            ],
        })
        report = audit.build_report(client, "Universidad Torcuato Di Tella")
        offers = [i for i in report["pendientes"] if i["entidad_tipo"] == "ofertas_academicas"]
        self.assertEqual({i["entidad_id"] for i in offers}, {"o1"})


class UnpublishedTests(unittest.TestCase):
    """What the adapter declared unpublished is reported apart from the backlog."""

    def _with_artifact(self, quality: dict) -> None:
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        path = Path(self.folder.name) / "x.json"
        path.write_text(json.dumps({"control_calidad": quality}), encoding="utf-8")
        original = dict(audit.ARTIFACTS)
        audit.ARTIFACTS["Universidad Austral"] = path
        self.addCleanup(lambda: audit.ARTIFACTS.update(original))

    def test_a_declared_section_is_not_backlog(self) -> None:
        self._with_artifact({"materias_sin_anio": {"motivo": "los planes son cuadros"}})
        client = _Client({
            "universidades": UNIVERSITIES,
            "materias": [{"id": "m1", "universidad_id": "u2", "anio_cursada": None}],
        })
        report = audit.build_report(client, "Universidad Austral")
        self.assertEqual([i for i in report["pendientes"] if i["campo"] == "anio_cursada"], [])
        self.assertEqual(len(report["no_publicado"]), 1)
        self.assertIn("los planes son cuadros", report["no_publicado"][0]["motivo"])

    def test_an_empty_table_the_university_does_not_publish_is_not_backlog(self) -> None:
        self._with_artifact({"secciones_sin_fuente_publica": {
            "aranceles": "no hay arancel publicado"}})
        client = _Client({"universidades": UNIVERSITIES})
        report = audit.build_report(client, "Universidad Austral")
        fees = [i for i in report["no_publicado"] if i["entidad_tipo"] == "aranceles"]
        self.assertEqual(len(fees), 1)
        self.assertNotIn("aranceles", {i["entidad_tipo"] for i in report["pendientes"]})

    def test_without_an_artifact_everything_stays_backlog(self) -> None:
        client = _Client({
            "universidades": UNIVERSITIES,
            "materias": [{"id": "m1", "universidad_id": "u2", "anio_cursada": None}],
        })
        original = dict(audit.ARTIFACTS)
        audit.ARTIFACTS["Universidad Austral"] = Path("/no/existe.json")
        self.addCleanup(lambda: audit.ARTIFACTS.update(original))
        report = audit.build_report(client, "Universidad Austral")
        # Nothing is excused, so the empty tables and the field are all backlog.
        self.assertEqual(report["no_publicado"], [])
        self.assertIn("anio_cursada", {i["campo"] for i in report["pendientes"]})
        self.assertIn("aranceles", {i["entidad_tipo"] for i in report["pendientes"]})


class EnrichmentTests(unittest.TestCase):
    def test_a_person_without_a_public_profile_is_not_a_pending_task(self) -> None:
        client = _Client({
            "universidades": UNIVERSITIES,
            "personas": [
                {"id": "p1", "universidad_id": "u1", "perfil_url": None,
                 "formacion": None, "biografia": None},
                {"id": "p2", "universidad_id": "u1", "perfil_url": "https://x",
                 "formacion": None, "biografia": None},
            ],
        })
        report = audit.build_report(client, "Universidad Torcuato Di Tella")
        people = [i for i in report["pendientes"] if i["entidad_tipo"] == "personas"]
        self.assertEqual({i["entidad_id"] for i in people}, {"p2"})
        self.assertEqual(len(people), 2)  # formacion and biografia


class SlugTests(unittest.TestCase):
    def test_each_university_writes_its_own_report(self) -> None:
        self.assertEqual(audit._slug("Universidad Torcuato Di Tella"), "utdt")
        self.assertEqual(audit._slug("Universidad de San Andrés"), "udesa")
        self.assertEqual(audit._slug("Universidad Austral"), "austral")
        self.assertEqual(audit._slug("Universidad Nueva"), "universidad_nueva")
