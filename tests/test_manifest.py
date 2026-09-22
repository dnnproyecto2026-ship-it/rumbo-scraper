"""Tests for the reproducible artifact manifest."""

import json
import tempfile
import unittest
from pathlib import Path

from rumbo_scraper.manifest import build_manifest, compare, count_collections, latest_manifest


class CountCollectionsTests(unittest.TestCase):
    def test_counts_every_list_by_dotted_path(self) -> None:
        payload = {"datos": {"carreras": [1, 2, 3], "aranceles": []},
                   "control_calidad": {"errores_descarga": [1]}}
        self.assertEqual(
            count_collections(payload),
            {"datos.carreras": 3, "datos.aranceles": 0, "control_calidad.errores_descarga": 1},
        )

    def test_does_not_descend_into_rows(self) -> None:
        payload = {"datos": {"carreras": [{"materias": [1, 2]}]}}
        self.assertEqual(count_collections(payload), {"datos.carreras": 1})


class BuildManifestTests(unittest.TestCase):
    def test_records_hash_size_and_counts_without_the_values(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "universidad.json"
            path.write_text(json.dumps({"datos": {"carreras": [{"nombre": "Abogacía"}]}}))
            manifest = build_manifest(Path(folder))
            entry = manifest["artefactos"]["universidad.json"]
            self.assertEqual(entry["conteos"], {"datos.carreras": 1})
            self.assertEqual(len(entry["sha256"]), 64)
            self.assertNotIn("Abogacía", json.dumps(manifest))

    def test_invalid_json_is_reported_instead_of_raising(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "roto.json").write_text("{no es json")
            entry = build_manifest(Path(folder))["artefactos"]["roto.json"]
            self.assertIn("error", entry)
            self.assertNotIn("conteos", entry)


class CompareTests(unittest.TestCase):
    def _manifest(self, count: int) -> dict[str, object]:
        return {"artefactos": {"u.json": {"conteos": {"datos.materias": count}}}}

    def test_reports_the_relative_drop(self) -> None:
        changes = compare(self._manifest(829), self._manifest(20))
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["antes"], 829)
        self.assertEqual(changes[0]["ahora"], 20)
        self.assertAlmostEqual(changes[0]["caida"], (829 - 20) / 829)

    def test_growth_is_a_change_but_not_a_drop(self) -> None:
        self.assertEqual(compare(self._manifest(13), self._manifest(14))[0]["caida"], 0.0)

    def test_identical_manifests_report_nothing(self) -> None:
        self.assertEqual(compare(self._manifest(13), self._manifest(13)), [])

    def test_a_missing_artifact_is_reported(self) -> None:
        changes = compare(self._manifest(13), {"artefactos": {}})
        self.assertEqual(changes[0]["detalle"], "artefacto ausente")


class LatestManifestTests(unittest.TestCase):
    def test_returns_none_without_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            self.assertIsNone(latest_manifest(Path(folder)))

    def test_returns_the_newest_by_name(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            (base / "20260101T000000Z.json").write_text('{"artefactos": {"a": {}}}')
            (base / "20260202T000000Z.json").write_text('{"artefactos": {"b": {}}}')
            path, payload = latest_manifest(base)
            self.assertEqual(path.name, "20260202T000000Z.json")
            self.assertEqual(list(payload["artefactos"]), ["b"])
