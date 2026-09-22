"""Tests for the safe Supabase loader preview."""

import json
from pathlib import Path
import tempfile
import unittest

from rumbo_scraper.database.load_utdt import (
    _boolean, _subject_identity, load_file, preview,
)


class LoadUTDTTests(unittest.TestCase):
    def test_boolean_normalization(self) -> None:
        self.assertTrue(_boolean("Sí"))
        self.assertFalse(_boolean("No"))
        self.assertIsNone(_boolean(None))

    def test_preview_validates_and_skips_unavailable_sections(self) -> None:
        source = Path("data/utdt_completo.json")
        dataset = json.loads(source.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "utdt.json"
            path.write_text(json.dumps(dataset), encoding="utf-8")
            loaded = load_file(path)
        counts = preview(loaded)
        self.assertEqual(counts["carreras"], 13)
        self.assertNotIn("turnos_anio", counts)
        self.assertNotIn("aranceles", counts)

    def test_subject_identity_is_stable_for_cosmetic_name_changes(self) -> None:
        first = {
            "carrera_id": "career-1", "posgrado_id": None,
            "nombre_materia": "Introducción a la Economía", "anio_cursada": 1,
        }
        second = {
            "carrera_id": "career-1", "posgrado_id": None,
            "nombre_materia": "  INTRODUCCION A LA ECONOMIA ", "anio_cursada": 1,
        }
        self.assertEqual(_subject_identity(first), _subject_identity(second))


if __name__ == "__main__":
    unittest.main()


class SelectAllTests(unittest.TestCase):
    """PostgREST caps an unbounded select; the loader must read past it."""

    class _Query:
        def __init__(self, rows: list[dict[str, object]]) -> None:
            self.rows = rows
            self.ranges: list[tuple[int, int]] = []
            self.ordered_by: str | None = None
            self._slice: list[dict[str, object]] = []

        def order(self, column: str) -> "SelectAllTests._Query":
            self.ordered_by = column
            return self

        def range(self, start: int, end: int) -> "SelectAllTests._Query":
            self.ranges.append((start, end))
            self._slice = self.rows[start:end + 1]
            return self

        def execute(self) -> object:
            return type("Response", (), {"data": self._slice})()

    def test_reads_every_page_until_a_short_one(self) -> None:
        from rumbo_scraper.database.supabase import select_all
        query = self._Query([{"id": index} for index in range(2500)])
        rows = select_all(query, size=1000)
        self.assertEqual(len(rows), 2500)
        self.assertEqual(query.ranges, [(0, 999), (1000, 1999), (2000, 2999)])

    def test_a_single_short_page_stops_immediately(self) -> None:
        from rumbo_scraper.database.supabase import select_all
        query = self._Query([{"id": 1}])
        self.assertEqual(len(select_all(query, size=1000)), 1)
        self.assertEqual(query.ranges, [(0, 999)])

    def test_an_exact_multiple_still_terminates(self) -> None:
        from rumbo_scraper.database.supabase import select_all
        query = self._Query([{"id": index} for index in range(1000)])
        self.assertEqual(len(select_all(query, size=1000)), 1000)
        self.assertEqual(query.ranges, [(0, 999), (1000, 1999)])

    def test_an_empty_table_returns_nothing(self) -> None:
        from rumbo_scraper.database.supabase import select_all
        self.assertEqual(select_all(self._Query([]), size=1000), [])

    def test_pages_are_ordered_so_they_cannot_overlap(self) -> None:
        # Without a total order PostgreSQL may return a row on two consecutive
        # pages and omit another, which was observed on a 1289-row table.
        from rumbo_scraper.database.supabase import select_all
        query = self._Query([{"id": index} for index in range(1500)])
        select_all(query, size=1000)
        self.assertEqual(query.ordered_by, "id")
