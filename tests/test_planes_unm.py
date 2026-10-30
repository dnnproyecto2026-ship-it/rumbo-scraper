import unittest

from rumbo_scraper.parsers.planes_sitios import plan_unm

TEXTO = """
Año     Cuat.    Código                    Asignatura-Actividad                 Correlativas
                                                                                                   Semanales      Teóricas   Prácticas   Talleres   Totales

  1       1       2111       Matemática I                                                              5             48         32                      80
  1       1       2114       Inglés I                                                                  3                                   48           48
  1       2       2116       Química Ambiental I                                    2112               5             48         32                      80
  2       3       2123       Derecho Ambiental                                      2113               5             80                                 80
  2       4       2126       Química Ambiental II                                   2116               5             48         32                      80
  5      9-10     2154       Taller de Práctica Pre-profesional (***)               2145             (****)          16         32         112         160
Ciclo de Formación Profesional                                                                                                                        1344
"""


class PlanUnm(unittest.TestCase):
    def test_una_fila_por_materia_con_su_anio(self):
        self.assertEqual(plan_unm(TEXTO), [
            ("Matemática I", 1), ("Inglés I", 1), ("Química Ambiental I", 1),
            ("Derecho Ambiental", 2), ("Química Ambiental II", 2),
            ("Taller de Práctica Pre-profesional", 5)])

    def test_una_optativa_sin_nombre_no_se_toma(self):
        self.assertEqual(plan_unm(TEXTO.replace("Derecho Ambiental", "Asignatura Optativa")), [])

    def test_un_codigo_repetido_no_se_toma(self):
        self.assertEqual(plan_unm(TEXTO.replace("2126", "2123")), [])

    def test_un_anio_que_vuelve_atras_no_se_toma(self):
        self.assertEqual(plan_unm(TEXTO.replace("  2       3       2123", "  1       3       2123")
                                  .replace("  1       2       2116", "  3       2       2116")), [])
