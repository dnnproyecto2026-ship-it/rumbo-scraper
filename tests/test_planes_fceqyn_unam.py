import unittest
from unittest import mock

from rumbo_scraper.parsers.planes_sitios import plan_fceqyn_unam

_CABECERA = [["", "", ""], ["COD", "ASIGNATURA", "REGIMEN"], ["", "", ""]]
_VACIA = ["", "", ""]


def _leer(*paginas):
    pdf = mock.MagicMock()
    pdf.__enter__.return_value.pages = [mock.Mock(extract_tables=mock.Mock(return_value=[_CABECERA + filas]))
                                        for filas in paginas]
    with mock.patch("pdfplumber.open", return_value=pdf):
        return plan_fceqyn_unam("grilla.pdf")


class PlanFceqynUnam(unittest.TestCase):
    def test_nombre_partido_arriba_y_abajo_del_codigo(self):
        self.assertEqual(_leer([
            ["PRIMER AÑO", "", ""],
            ["", "Introducción a la Ingeniería", ""], ["01", "", "Cuatrimestral"], ["", "de los Alimentos", ""], _VACIA,
            ["03", "Análisis I", "Cuatrimestral"],
            ["SEGUNDO AÑO", "", ""],
            ["06", "Química Inorgánica", "Cuatrimestral"],
        ]), [("Introducción a la Ingeniería de los Alimentos", 1), ("Análisis I", 1), ("Química Inorgánica", 2)])

    def test_filas_seguidas_sin_linea_en_blanco_se_reparten_por_simetria(self):
        self.assertEqual(_leer([
            ["PRIMER AÑO", "", ""], ["SEGUNDO AÑO", "", ""], ["TERCER AÑO", "", ""], ["CUARTO AÑO", "", ""],
            ["QUINTO AÑO", "", ""],
            ["35", "Control de Procesos", "Cuatrimestral"],
            ["", "Operaciones de", ""], ["36", "Transferencia de Masa en", "Cuatrimestral"], ["", "Alimentos", ""],
        ]), [("Control de Procesos", 5), ("Operaciones de Transferencia de Masa en Alimentos", 5)])

    def test_nombre_cortado_por_el_salto_de_pagina(self):
        self.assertEqual(_leer(
            [["PRIMER AÑO", "", ""], ["SEGUNDO AÑO", "", ""], ["TERCER AÑO", "", ""], ["CUARTO AÑO", "", ""],
             ["22", "Operaciones de", "C"], ["", "Movimiento", ""], _VACIA, ["23", "Fundamentos de", "C"]],
            [["", "Transferencia de Calor", ""], ["", "Economía, Organización y", ""], ["24", "", "C"],
             ["", "Legislación", ""], _VACIA, ["25", "Estadística Aplicada", "C"]],
        ), [("Operaciones de Movimiento", 4), ("Fundamentos de Transferencia de Calor", 4),
            ("Economía, Organización y Legislación", 4), ("Estadística Aplicada", 4)])

    def test_termina_en_el_pie_y_no_toma_cursos_repetidos_ni_tesis(self):
        self.assertEqual(_leer([
            ["PRIMER AÑO", "", ""],
            ["1.1.", "Biología General", "A"],
            ["1.2.", "Curso de Orientación Regional (*)", "A"], ["1.3.", "Curso de Orientación Regional (*)", "A"],
            _VACIA, ["", "Tesis de Grado", ""],
            ["TÍTULO: LICENCIADO/A EN GENETICA", None, None], ["3.1.", "No entra", "A"],
        ]), [("Biología General", 1)])

    def test_anios_fuera_de_orden_no_dan_nada(self):
        self.assertEqual(_leer([["SEGUNDO AÑO", "", ""], ["1", "Algo", "A"]]), [])
