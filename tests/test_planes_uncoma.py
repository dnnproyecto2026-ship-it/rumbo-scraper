import unittest

from rumbo_scraper.parsers.planes_sitios import plan_uncoma_listado

TEXTO = """
Año              Orden   Asignatura                                          Carácter
Primer año
1 cuatrimestre   1       Legislación                                         cuatrimestral
2 cuatrimestre   2       Biología                                            cuatrimestral
Segundo año
1 cuatrimestre   3       Informática Aplicada                                anual
"""


class PlanUncomaListado(unittest.TestCase):
    def test_anio_por_su_titulo(self):
        self.assertEqual(plan_uncoma_listado(TEXTO), [
            ("Legislación", 1), ("Biología", 1), ("Informática Aplicada", 2)])

    def test_un_numero_salteado_no_se_toma(self):
        self.assertEqual(plan_uncoma_listado(TEXTO.replace(" 3  ", " 4  ")), [])
