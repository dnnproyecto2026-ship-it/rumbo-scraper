"""Tests for the plan read off a table of four-month terms (FIUBA)."""

import unittest

from rumbo_scraper.parsers.plan_por_cuatrimestre import leer_filas

CBC = [
    ["Ciclo Básico Común", "", "", ""],
    ["Primer y segundo cuatrimestre", "", "", ""],
    ["Código", "Asignaturas obligatorias", "Carga Horaria Semanal", "Carga Horaria Total"],
    ["66", "Análisis Matemático A", "9", "144"],
    ["62", "Álgebra A", "9", "144"],
    ["Carga horaria total", "", "38", "608"],
]


class LeerElPlan(unittest.TestCase):
    def test_el_cbc_es_el_primer_anio_y_cada_par_de_cuatrimestres_otro(self):
        filas = CBC + [
            ["TERCER CUATRIMESTRE", "", "", ""],
            ["Análisis Matemático II", "8", "128", "CBC"],
            ["Total Créditos", "20", "320", ""],
            ["QUINTO CUATRIMESTRE", "", "", ""],
            ["Sistemas Operativos", "6", "96", "Organización del Computador"],
            ["TOTAL CRÉDITOS DEL PLAN", "226", "", ""],
        ]
        self.assertEqual(leer_filas(filas), [
            ("Análisis Matemático A", 1), ("Álgebra A", 1),
            ("Análisis Matemático II", 2), ("Sistemas Operativos", 3)])

    def test_lo_que_sigue_al_total_del_plan_no_es_del_plan(self):
        filas = CBC + [
            ["TERCER CUATRIMESTRE"], ["Física", "6", "96", "CBC"],
            ["Total de Créditos y Horas del Plan", "231", "3696"],
            ["Criptografía I", "6", "96", "Álgebra Lineal"],  # an elective
            ["PRIMER CUATRIMESTRE"], ["Química", "6", "96", ""],  # the old plan
        ]
        self.assertNotIn("Criptografía I", [m for m, _ in leer_filas(filas)])
        self.assertNotIn("Química", [m for m, _ in leer_filas(filas)])

    def test_un_nombre_largo_sigue_en_la_fila_de_abajo(self):
        filas = CBC + [
            ["UNDÉCIMO CUATRIMESTRE"],
            ["Gerenciamiento y Organización de", "4", "", "Economía"],
            ["", "64", "", ""],
            ["Obras Civiles", "", "", ""],
        ]
        self.assertIn(("Gerenciamiento y Organización de Obras Civiles", 6), leer_filas(filas))

    def test_sin_el_encabezado_de_un_cuatrimestre_el_subtotal_lo_marca(self):
        filas = CBC + [
            ["CUARTO CUATRIMESTRE"], ["Álgebra Lineal", "8", "128", "CBC"],
            ["Total Cuatrimestre"], ["22", "352"],
            ["Señales y Sistemas", "6", "96", "Álgebra Lineal"],  # term 5, no heading
        ]
        self.assertIn(("Álgebra Lineal", 2), leer_filas(filas))
        self.assertIn(("Señales y Sistemas", 3), leer_filas(filas))

    def test_ni_la_opcion_ni_las_electivas_ni_un_encabezado_pegado(self):
        filas = CBC + [
            ["NOVENO CUATRIMESTRE"],
            ["Tesis de Ingeniería Informática", "6 de 12", "96", ""],
            ["ó", "", "", ""],
            ["Electivas/optativas", "12", "192", ""],
            ["Introducción a la Ingeniería Mecánica CRÉDITOS (carga", "4", "64", ""],
        ]
        self.assertEqual([m for m, _ in leer_filas(filas)][2:], [
            "Tesis de Ingeniería Informática", "Introducción a la Ingeniería Mecánica"])

    def test_el_cbc_sin_codigos(self):
        filas = [["Ciclo Básico Común"], ["Primer y segundo cuatrimestre"],
                 ["Introducción al Pensamiento Científico", "4", "64"]]
        self.assertEqual(leer_filas(filas), [("Introducción al Pensamiento Científico", 1)])

    def test_cuatrimestres_con_numero(self):
        filas = CBC + [["3° Cuatrimestre"], ["Sistemas de Coordenadas", "4", "64", "CBC"],
                       ["Total de Créditos / Horas", "23", "368"],
                       ["4° Cuatrimestre"], ["Cartografía", "6", "96", ""]]
        self.assertEqual(leer_filas(filas)[2:], [("Sistemas de Coordenadas", 2), ("Cartografía", 2)])


if __name__ == "__main__":
    unittest.main()
