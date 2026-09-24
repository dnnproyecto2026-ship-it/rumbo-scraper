"""Tests for the plan whose cycles announce how many subjects they have."""

import unittest

from rumbo_scraper.parsers.plan_por_ciclos import leer


class LeerPorCiclos(unittest.TestCase):
    def test_un_ciclo_con_tantas_materias_como_anuncia(self):
        self.assertEqual(leer([
            "Ciclo Básico Común (CBC): Seis (2) materias.",
            "Introducción al Pensamiento Científico", "Sociología",
            "Ciclo General: Veintidós (3) asignaturas.",
            "Teoría Política y Social I", "Historia Argentina", "Opinión Pública",
        ]), ["Introducción al Pensamiento Científico", "Sociología",
             "Teoría Política y Social I", "Historia Argentina", "Opinión Pública"])

    def test_si_no_siguen_las_materias_anunciadas_no_se_toma_nada(self):
        self.assertEqual(leer([
            "Ciclo Orientado: Cinco (5) materias.",
            "Dos (2) materias electivas a elegir entre las tres (3) por orientación.",
        ]), [])

    def test_el_resumen_de_arriba_no_es_la_lista(self):
        self.assertEqual(leer([
            "Ciclo Básico Común (CBC): Seis (2) materias.",
            "Ciclo General: Veintidós (22) asignaturas.",
            "Ciclo Orientado: Cinco (5) materias.",
        ]), [])


    def test_un_ciclo_obligatorio_sin_su_lista_deja_el_plan_vacio(self):
        self.assertEqual(leer([
            "Núcleo Básico Obligatorio: 2 asignaturas", "Contabilidad I Básica", "Matemáticas",
            "Núcleo Profesional Obligatorio: 3 asignaturas", "Marketing",
        ]), [])

    def test_el_nucleo_electivo_no_es_del_plan(self):
        self.assertEqual(leer([
            "Núcleo Básico Obligatorio: 2 asignaturas", "Contabilidad I Básica", "Matemáticas",
            "Núcleo Electivo: 2 asignaturas", "Negocios Digitales", "Comercio Exterior",
        ]), ["Contabilidad I Básica", "Matemáticas"])


if __name__ == "__main__":
    unittest.main()
