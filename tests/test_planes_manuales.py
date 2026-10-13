import unittest

from rumbo_scraper.database.planes_manuales import materias_de


class MateriasDe(unittest.TestCase):
    def test_year_and_name(self):
        self.assertEqual(materias_de("1 | Introducción al Derecho\n\n2 | Derecho Civil I"),
                         [("Introducción al Derecho", 1), ("Derecho Civil I", 2)])

    def test_name_alone(self):
        self.assertEqual(materias_de("Matemática\nFísica"), [("Matemática", None), ("Física", None)])

    def test_mixed_or_unreadable_lines_are_sent_back(self):
        self.assertIsInstance(materias_de("1 | Matemática\nFísica"), str)
        self.assertIsInstance(materias_de("1 | Matemática | anual"), str)


if __name__ == "__main__":
    unittest.main()
