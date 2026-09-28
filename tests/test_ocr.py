import unittest

from rumbo_scraper.parsers.ocr import plan_escaneado, vocabulario

CONOCIDAS = vocabulario({"Álgebra Lineal", "Física I", "Física II", "Química General", "Análisis Matemático I",
                         "Inglés Técnico", "Estadística"})


class PlanEscaneado(unittest.TestCase):
    def test_corrige_la_lectura_con_la_materia_conocida(self):
        texto = """PRIMER AÑO
FB1 Álgebra Lineai A 6,0 96
FB2 Fisica I A 7,0 112
Química General A 5,0 80
SEGUNDO AÑO
FB5 Fisica II A 7,0 112 FB2
Análisis Matemático l A 6,0 96"""
        self.assertEqual(plan_escaneado(texto, CONOCIDAS),
                         [("Álgebra Lineal", 1), ("Física I", 1), ("Química General", 1), ("Física II", 2),
                          ("Análisis Matemático I", 2)])

    def test_un_encabezado_perdido_descarta_el_plan(self):
        texto = "PRIMER CUATRIMESTRE\nFísica I\nA EGUNDO IMEST\nFísica II\nTERCER CUATRIMESTRE\nEstadística"
        self.assertEqual(plan_escaneado(texto, CONOCIDAS), [])

    def test_una_fila_sin_nombre_legible_descarta_el_plan(self):
        texto = "PRIMER AÑO\nFísica I\nQuímica General\nC6 A 4,0 54 FB8\nEstadística"
        self.assertEqual(plan_escaneado(texto, CONOCIDAS), [])

    def test_por_cuatrimestres(self):
        texto = "PRIMER CUATRIMESTRE\nFísica I\nSEGUNDO CUATRIMESTRE\nQuímica General\nTERCER CUATRIMESTRE\nEstadística"
        self.assertEqual(plan_escaneado(texto, CONOCIDAS), [("Física I", 1), ("Química General", 1), ("Estadística", 2)])


if __name__ == "__main__":
    unittest.main()
