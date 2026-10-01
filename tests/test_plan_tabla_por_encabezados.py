import unittest

from rumbo_scraper.parsers.planes_sitios import plan_tabla_por_encabezados


class PlanTablaPorEncabezados(unittest.TestCase):
    def test_anio_en_una_fila_propia_sin_nivelacion_ni_optativas(self):
        html = """<table><tr><td>PRIMER AÑO</td></tr>
        <tr><td>Código</td><td>Nombre</td><td>Duración</td></tr>
        <tr><td>CNE</td><td>Expresión de Problemas</td><td>6 Semanas</td></tr>
        <tr><td>SI106</td><td>Conceptos de Algoritmos</td><td>Semestral</td></tr>
        <tr><td>SEGUNDO AÑO</td></tr>
        <tr><td>SI201</td><td>Redes y Comunicaciones (Sexto Semestre)</td><td>Semestral</td></tr>
        <tr><td>ELEGIR DOS OPTATIVAS SEGÚN LA ORIENTACIÓN</td></tr>
        <tr><td>X1</td><td>Big Data</td><td>Semestral</td></tr></table>"""
        self.assertEqual(plan_tabla_por_encabezados(html),
                         [("Conceptos de Algoritmos", 1), ("Redes y Comunicaciones", 2)])

    def test_columna_de_anio_con_una_celda_que_abarca_filas(self):
        html = """<table><tr><td>CICLOS</td><td>CURSOS</td><td>SEMESTRE</td><td>AÑO</td><td>HORAS</td></tr>
        <tr><td rowspan="2">CICLO</td><td>Contabilidad I</td><td>1</td><td>1º</td><td>128</td></tr>
        <tr><td>Matemática I</td><td>2</td><td>1º</td><td>96</td></tr>
        <tr><td>CICLO II</td><td>Costos</td><td>3</td><td>2º</td><td>96</td></tr></table>"""
        self.assertEqual(plan_tabla_por_encabezados(html),
                         [("Contabilidad I", 1), ("Matemática I", 1), ("Costos", 2)])


if __name__ == "__main__":
    unittest.main()
