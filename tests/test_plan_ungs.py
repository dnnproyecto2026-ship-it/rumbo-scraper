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
    def test_los_talleres_iniciales_y_dos_semestres_son_el_primer_anio(self):
        self.assertEqual(plan_ungs(ITINERARIO), [("Taller de tecnología", 1), ("Química general", 1),
                                                 ("Física I", 1), ("Física II", 1), ("Termodinámica", 2)])

    def test_varias_asignaturas_en_un_mismo_item(self):
        html = ITINERARIO.replace("<li>Física II</li>", "<li>Física II<br />Taller de radio I<br/> Óptica</li>")
        self.assertIn(("Taller de radio I", 1), plan_ungs(html))
        self.assertIn(("Óptica", 1), plan_ungs(html))
        self.assertNotIn("Física II Taller de radio I", [n for n, _ in plan_ungs(html)])

    def test_un_nombre_partido_en_dos_lineas_es_uno(self):
        html = ITINERARIO.replace("<li>Física II</li>", "<li>Cartografía y Sistemas de<br/>Información Geográfica</li>")
        self.assertIn(("Cartografía y Sistemas de Información Geográfica", 1), plan_ungs(html))

    def test_solo_el_itinerario_que_arranca_en_el_segundo_semestre(self):
        html = """<table><tr><td>2) INICIANDO LA CARRERA EN EL SEGUNDO SEMESTRE</td></tr>
        <tr><td><h1>1</h1></td><td><ul><li>Cartografía</li></ul></td></tr>
        <tr><td><h1>2</h1></td><td><ul><li>Geodesia</li></ul></td></tr>
        <tr><td><h1>3</h1></td><td><ul><li>Teledetección</li></ul></td></tr>
        <tr><td><h1>4</h1></td><td><ul><li>SIG</li></ul></td></tr></table>"""
        self.assertEqual(plan_ungs(html), [("Cartografía", 1), ("Geodesia", 1), ("Teledetección", 1), ("SIG", 2)])

    def test_sin_itinerario_no_hay_plan(self):
        self.assertEqual(plan_ungs("<table><tr><td>Asignatura</td></tr></table>"), [])


if __name__ == "__main__":
    unittest.main()
