import unittest

from rumbo_scraper.database.completar_duraciones import duracion_leida

USAL = """<html><body><main><h1>Martillero y Corredor Universitario</h1>
<p>Título:</p><p>Martillero y Corredor Universitario</p>
<p>(2 años y 1 cuatrimestre)</p></main></body></html>"""


class DuracionLeidaTest(unittest.TestCase):
    def test_usal_reads_the_brackets_beside_the_degree(self):
        self.assertEqual(duracion_leida(USAL, "USAL"), 2.5)

    def test_another_university_does_not_use_usal_reader(self):
        self.assertIsNone(duracion_leida(USAL, "UNLP"))

    def test_the_general_reader_answers_first(self):
        html = "<html><body><p>La carrera tiene una duración de 4 años.</p><p>(2 años)</p></body></html>"
        self.assertEqual(duracion_leida(html, "USAL"), 4)


if __name__ == "__main__":
    unittest.main()
