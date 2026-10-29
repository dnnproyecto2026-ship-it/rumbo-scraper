import unittest

from rumbo_scraper.database.institutos_faltantes import _ya_esta_por_nombre, cue7


class Cue(unittest.TestCase):
    def test_el_cue_son_los_siete_primeros_digitos_del_cueanexo(self):
        self.assertEqual(cue7("062176900"), "0621769")
        self.assertEqual(cue7("5001301"), "5001301")
        self.assertEqual(cue7("201644"), "0201644")
        self.assertIsNone(cue7(None))

    def test_sin_cue_se_compara_nombre_y_numero(self):
        conocidos = ["instituto superior 6 de cordoba"]
        self.assertTrue(_ya_esta_por_nombre("Instituto Superior N° 6 de Córdoba", conocidos))
        self.assertFalse(_ya_esta_por_nombre("Instituto Superior N° 7 de Córdoba", conocidos))
