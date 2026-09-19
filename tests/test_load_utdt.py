"""Tests for the safe Supabase loader preview."""

import json
from pathlib import Path
import tempfile
import unittest

from rumbo_scraper.database.load_utdt import _boolean, load_file, preview


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


if __name__ == "__main__":
    unittest.main()
