import unittest

from rumbo_scraper.parsers.planes_sitios import plan_ffyb_uba

TEXTO = """
 1° Cuatrimestre           Carácter       Duración      Horas
 01. Matemática (51)       Obligatoria    Cuatrimestral 6          96
 03. Introducción al       Obligatoria    Cuatrimestral 4          64
 Conocimiento de la
 Sociedad y el Estado (24)
Estas asignaturas corresponden al Ciclo Básico Común.

 3° Cuatrimestre          Carácter       Duración        Horas
 07. Química General e    Obligatoria    Cuatrimestral   9       126     CBC
 Inorgánica                                                              aprobado
 26. Salud Pública e         Obligatoria   Cuatrimestral   6,5         91        TP 15
     Higiene Ambiental                                                           TP 20
 38. Asignatura Optativa 1      Optativa       Bimestral             5
 46.Salud Mental            Obligatoria    Bimestral        5
13) Carga horaria lectiva total
 01. Otra cosa
"""


class PlanFfybUba(unittest.TestCase):
    def test_por_cuatrimestre_con_sus_nombres_partidos(self):
        self.assertEqual(plan_ffyb_uba(TEXTO), [
            ("Matemática", 1), ("Introducción al Conocimiento de la Sociedad y el Estado", 1),
            ("Química General e Inorgánica", 2), ("Salud Pública e Higiene Ambiental", 2),
            ("Salud Mental", 2)])


if __name__ == "__main__":
    unittest.main()
