import unittest

from rumbo_scraper.parsers.uai import parse_plan


class PlanUai(unittest.TestCase):
    def test_materias_anuales_es_el_regimen_y_no_una_materia(self):
        html = ("<div><p>1er año</p><p>Materias anuales</p><p>MUSICOTERAPIA I</p>"
                "<p>ANTROPOLOGÍA</p><p>2do año</p><p>Materias anuales</p><p>MUSICOTERAPIA II</p></div>")
        materias = parse_plan(html, "Licenciatura en Musicoterapia")
        self.assertEqual([m["nombre_materia"] for m in materias],
                         ["MUSICOTERAPIA I", "ANTROPOLOGÍA", "MUSICOTERAPIA II"])
        self.assertEqual({m["regimen"] for m in materias}, {"Anual"})


if __name__ == "__main__":
    unittest.main()
