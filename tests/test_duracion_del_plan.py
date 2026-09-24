"""Tests for the duration a grado plan gives its career."""

import unittest

from rumbo_scraper.database.completar_duraciones import duracion_del_plan


class DuracionDelPlan(unittest.TestCase):
    def test_un_plan_con_todos_sus_anios_completos(self):
        self.assertEqual(duracion_del_plan({1: 8, 2: 8, 3: 8, 4: 8, 5: 7}), 5)

    def test_el_ultimo_anio_de_tesis_no_es_un_anio(self):
        self.assertIsNone(duracion_del_plan({1: 10, 2: 10, 3: 11, 4: 9, 5: 3}))

    def test_un_anio_que_falta_no_se_completa(self):
        self.assertIsNone(duracion_del_plan({1: 8, 2: 8, 4: 8, 5: 8}))

    def test_fuera_de_cuatro_a_seis_anios_no_se_dice(self):
        self.assertIsNone(duracion_del_plan({1: 8, 2: 8, 3: 8}))
        self.assertIsNone(duracion_del_plan({a: 8 for a in range(1, 8)}))
