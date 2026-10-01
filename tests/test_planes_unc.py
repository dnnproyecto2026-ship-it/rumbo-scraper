import unittest

from rumbo_scraper.parsers.planes_sitios import plan_famaf, plan_por_semestres


class PlanPorSemestres(unittest.TestCase):
    def test_dos_semestres_por_anio_sin_el_ciclo_de_nivelacion(self):
        html = """<p><strong>:: CICLO DE NIVELACIÓN</strong></p><p>• Introducción a la Matemática</p>
        <p><strong>Primer semestre</strong><br/>• Matemática I<br/>• Contabilidad I</p>
        <p><strong>Segundo semestre</strong><br/>• Matemática II</p>
        <p><strong>Tercer semestre</strong><br/>• Estadística I.</p>
        <p>Diálogo con profesionales</p><p>• Otra cosa</p>"""
        self.assertEqual(plan_por_semestres(html), [("Matemática I", 1), ("Contabilidad I", 1),
                                                    ("Matemática II", 1), ("Estadística I", 2)])


class PlanFamaf(unittest.TestCase):
    def test_tarjetas_por_anio_sin_las_carreras_que_la_comparten(self):
        html = """<div class="year"><div class="label"><h2>1º año</h2></div>
        <div class="subject"><a href="/m/a">Análisis Matemático I (LC - LMA - LHM)</a><h2>1º año</h2></div></div>
        <div class="year"><div class="label"><h2>2º año</h2></div>
        <div class="subject"><a href="/m/b">Análisis Numérico</a></div></div>"""
        self.assertEqual(plan_famaf(html), [("Análisis Matemático I", 1), ("Análisis Numérico", 2)])


if __name__ == "__main__":
    unittest.main()
