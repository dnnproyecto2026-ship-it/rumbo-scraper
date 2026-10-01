import unittest

from rumbo_scraper.parsers.planes_sitios import plan_ungs

ITINERARIO = """
<table><tr><td>1) INICIANDO LA CARRERA EN EL PRIMER SEMESTRE</td></tr>
<tr><td>► PRIMER SEMESTRE DEL AÑO</td><td></td><td>► SEGUNDO SEMESTRE DEL AÑO</td></tr>
<tr><td><h1>1</h1></td><td><ul><li>Taller de tecnología</li><li>Química general</li></ul></td><td></td>
    <td><h1>2</h1></td><td><ul><li>Física I</li></ul></td></tr>
<tr><td><h1>3</h1></td><td><ul><li>Física II</li></ul></td><td></td>
    <td><h1>4</h1></td><td><ul><li>Termodinámica</li></ul></td></tr></table>
<table><tr><td>2) INICIANDO LA CARRERA EN EL SEGUNDO SEMESTRE</td></tr>
<tr><td></td><td></td><td><h1>1</h1></td><td><ul><li>Otra cosa</li></ul></td></tr></table>
"""


class PlanUngs(unittest.TestCase):
    def test_semestres_de_a_dos_por_anio_del_primer_itinerario(self):
        self.assertEqual(plan_ungs(ITINERARIO), [("Taller de tecnología", 1), ("Química general", 1),
                                                 ("Física I", 1), ("Física II", 2), ("Termodinámica", 2)])

    def test_sin_itinerario_no_hay_plan(self):
        self.assertEqual(plan_ungs("<table><tr><td>Asignatura</td></tr></table>"), [])


if __name__ == "__main__":
    unittest.main()
