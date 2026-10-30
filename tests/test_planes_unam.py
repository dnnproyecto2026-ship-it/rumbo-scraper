import unittest

from rumbo_scraper.parsers.planes_sitios import plan_unam_codigos

TEXTO = """
                         PRIMER AÑO
                                                  Total   Régimen
          ASIGNATURA          Condición
                                  Área Diseño
       Taller de práctica
1.1                             L-R-P         4            60       1C
       profesional I
       Taller de práctica
1.2                             L-R-P         4            60       2C            1.1
       profesional II
       Dibujo y
1.3                             L-R-P         3            45       1C
       Representación I
1.4    Morfología                L-R-P         3            45       2C
                                  Área Gestión
       Higiene y seguridad
1.5                             L-R-P         3            45       1C
       laboral
       Gestión de la
1.6    producción textil e      L-R-P         4            60       2C
       indumentaria
           Total Horas Reloj                   47           705
                         SEGUNDO AÑO
                                  Área Cultura
2.1    Historia                 L-R-P         3            45       1C
"""


class PlanUnamCodigos(unittest.TestCase):
    def test_nombres_partidos_alrededor_del_numero(self):
        self.assertEqual(plan_unam_codigos(TEXTO), [
            ("Taller de práctica profesional I", 1), ("Taller de práctica profesional II", 1),
            ("Dibujo y Representación I", 1), ("Morfología", 1), ("Higiene y seguridad laboral", 1),
            ("Gestión de la producción textil e indumentaria", 1), ("Historia", 2)])

    def test_un_numero_salteado_no_se_toma(self):
        self.assertEqual(plan_unam_codigos(TEXTO.replace("1.4    Morfología", "1.7    Morfología")), [])

    def test_un_numero_de_otro_anio_no_se_toma(self):
        self.assertEqual(plan_unam_codigos(TEXTO.replace("2.1    Historia", "1.7    Historia")), [])
