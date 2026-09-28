import unittest

from rumbo_scraper.database.planes_unicen import plan_por_celdas


class PlanPorCeldas(unittest.TestCase):
    def test_una_celda_por_materia_y_solo_el_plan_vigente(self):
        html = """<table><tr><td><h4>Primer Año</h4></td></tr><tr><td><h5>Primer Cuatrimestre</h5></td></tr>
        <tr><td>Análisis I</td></tr><tr><td>Ecuaciones Diferenciales<br /> Ordinarias</td></tr>
        <tr><td><h4>Segundo Año</h4></td></tr><tr><td>Formativa Técnica (Optativa)</td></tr><tr><td>Análisis II</td></tr>
        <tr><td><h4>Primer Año</h4></td></tr><tr><td>Plan Anterior</td></tr></table>"""
        self.assertEqual(plan_por_celdas(html),
                         [("Análisis I", 1), ("Ecuaciones Diferenciales Ordinarias", 1), ("Análisis II", 2)])


if __name__ == "__main__":
    unittest.main()
