import unittest

from rumbo_scraper.database.completar_uspt import duracion_de


class CompletarUspt(unittest.TestCase):
    def test_duracion_en_sus_formas(self):
        self.assertEqual(duracion_de("4 año/s"), 4)
        self.assertEqual(duracion_de("2 años y medio"), 2.5)
        self.assertEqual(duracion_de("4"), 4)
        self.assertEqual(duracion_de("3 años"), 3)
        self.assertIsNone(duracion_de("1600 horas"))
        self.assertIsNone(duracion_de(None))


if __name__ == "__main__":
    unittest.main()
