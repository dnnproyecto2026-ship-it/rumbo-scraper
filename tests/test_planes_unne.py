import unittest

from rumbo_scraper.parsers.planes_sitios import plan_bloques_numerados

TEXTO = """   Año        Caracter                         Código. Asignatura              Correlativa

                               1. Introducción al derecho                         PNEA

Primer año    Obligatorias
                               2. Sociología                                       1


                               3. Derecho de las obligaciones                      2
Segundo año   Obligatorias
                               4. Derecho ﬁnanciero                                3
  Año       Caracter                        Código. Asignatura                        Correlativa
                           5. Ética profesional                                        4° año-3
Tercer año
                           A   36-A. Defensa del Estado en juicio                      4° año-29
"""


class PlanBloquesNumerados(unittest.TestCase):
    def test_el_anio_al_costado_del_bloque_sin_las_optativas_de_orientacion(self):
        self.assertEqual(plan_bloques_numerados(TEXTO), [
            ("Introducción al derecho", 1), ("Sociología", 1),
            ("Derecho de las obligaciones", 2), ("Derecho financiero", 2), ("Ética profesional", 3)])


if __name__ == "__main__":
    unittest.main()
