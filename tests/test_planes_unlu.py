import unittest
from unittest import mock

from rumbo_scraper.parsers.planes_sitios import plan_unlu_cuatrimestres


def _pagina(filas):
    """A page with one bordered table: (term cell height in rows, term,
    [(code, name)]) per term cell; the cells are 30 points high."""
    celdas, textos, y = [], {}, 100
    for alto, termino, rows in filas:
        izquierda = (50, y, 100, y + 30 * alto)
        celdas.append(izquierda)
        textos[izquierda] = termino
        for codigo, nombre in rows:
            celdas += [(100, y, 150, y + 30), (150, y, 400, y + 30)]
            textos[(100, y, 150, y + 30)] = codigo
            textos[(150, y, 400, y + 30)] = nombre
            y += 30
    pagina = mock.Mock()
    pagina.find_tables.return_value = [mock.Mock(cells=celdas)]
    pagina.crop.side_effect = lambda celda: mock.Mock(extract_text=lambda: textos[tuple(celda)])
    return pagina


def _leer(*paginas):
    pdf = mock.MagicMock()
    pdf.__enter__.return_value.pages = list(paginas)
    with mock.patch("pdfplumber.open", return_value=pdf):
        return plan_unlu_cuatrimestres("plan.pdf")


class PlanUnluCuatrimestres(unittest.TestCase):
    def test_numeral_de_la_celda_que_abarca_las_filas(self):
        pagina = _pagina([
            (2, "-", [("19054", "Competencias Básicas"), ("14026", "Taller Introductorio de\nProblemas")]),
            (3, "I", [("11271", "Introducción a la Programación"), ("13014", "Matemática Básica"),
                      ("21256", "Introducción a los Sistemas\nde Información")]),
            (2, "II", [("11274", "Programación Estructurada"), ("11256", "Sistemas de Información I")]),
            (1, "III", [("41407", "Organización de Computadoras")]),
        ])
        self.assertEqual(_leer(pagina), [
            ("Introducción a la Programación", 1), ("Matemática Básica", 1),
            ("Introducción a los Sistemas de Información", 1), ("Programación Estructurada", 1),
            ("Sistemas de Información I", 1), ("Organización de Computadoras", 2)])

    def test_celda_cortada_por_el_salto_de_pagina(self):
        primera = _pagina([(2, "II", [("11274", "Programación Estructurada"), ("11256", "Sistemas de Información I")])])
        segunda = _pagina([(1, "", [("13021", "Álgebra Lineal y Geometría")]),
                           (2, "III", [("11275", "Estructuras de Datos y Algoritmos I"),
                                       ("11258", "Sistemas de Información II")])])
        self.assertEqual(_leer(primera, segunda), [
            ("Programación Estructurada", 1), ("Sistemas de Información I", 1),
            ("Álgebra Lineal y Geometría", 1), ("Estructuras de Datos y Algoritmos I", 2),
            ("Sistemas de Información II", 2)])

    def test_tabla_de_equivalencias_no_es_el_plan(self):
        pagina = _pagina([(1, "(19054) Competencias", [("(11074)", "Programación I")])])
        self.assertEqual(_leer(pagina), [])


if __name__ == "__main__":
    unittest.main()
