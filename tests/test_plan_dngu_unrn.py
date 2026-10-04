import unittest

from rumbo_scraper.parsers.planes_sitios import plan_dngu

ANEXO = """COD         ASIGNATURA               REGIMEN        HORARIA HORARIA CORRELATIVAS
PRIMER AÑO
 1         Biología Celular    Cuatrimestral           5      80           -            Presencial
      Taller en Fundamentos de
 2                             Cuatrimestral           5      80           -            Presencial
            la Alimentación
SEGUNDO AÑO
                                                                   Curso nivelatorio-
 3            Fisiología               Anual           6     192                        Presencial
                                                                           1
         Prácticas en Nutrición
 4   Clínica y Administración de Cuatrimestral       12     192            23-34    Presencial
         Servicios Alimentarios
 5     Trabajo Final Integrador         ---           0     128           31 A 37   Presencial
TÍTULO: LICENCIADO/A EN NUTRICIÓN
"""


class AnexoUnrn(unittest.TestCase):
    def test_columna_de_correlativas_nombre_en_tres_renglones_y_fila_sin_regimen(self):
        self.assertEqual(plan_dngu(ANEXO), [
            ("Biología Celular", 1), ("Taller en Fundamentos de la Alimentación", 1), ("Fisiología", 2),
            ("Prácticas en Nutrición Clínica y Administración de Servicios Alimentarios", 2),
            ("Trabajo Final Integrador", 2)])


if __name__ == "__main__":
    unittest.main()
