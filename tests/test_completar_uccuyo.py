import unittest

from rumbo_scraper.database.completar_uccuyo import anios


class CompletarUccuyo(unittest.TestCase):
    def test_semestres_a_anios(self):
        self.assertEqual(anios("10"), 5)
        self.assertEqual(anios("5"), 2.5)
        self.assertIsNone(anios("1"))
        self.assertIsNone(anios(None))


if __name__ == "__main__":
    unittest.main()
