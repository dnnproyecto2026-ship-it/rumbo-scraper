"""Tests for the degree, duration and modality read off a postgraduate's page."""

import unittest

from rumbo_scraper.parsers.datos_posgrado import datos_de_posgrado, nombra_el_programa

LISTA_DE_DATOS = """
<html><head><title>Universidad Nacional de X</title></head><body>
<nav><a>Título: Magíster en Otra Cosa</a></nav>
<form><ul>
<li><strong>Duración: </strong>2 años</li>
<li><strong>Modalidad: </strong>Presencial</li>
<li><strong>Título de posgrado:</strong> Magíster en Ciencia de Datos</li>
</ul></form></body></html>
"""

ENCABEZADO_Y_TABLA = """
<html><body><main>
<h1>Doctorado en Ingeniería Civil</h1>
<h5>Título de Posgrado</h5><p>Doctor/a en Ingeniería Civil</p>
<table><tr><th>Carrera</th><th>Duración</th></tr>
<tr><td>Doctorado en Ingeniería Civil</td><td>5 años</td></tr></table>
<p>Título de Posgrado: Especialista en Estructuras</p>
</main></body></html>
"""


class DatosDePosgrado(unittest.TestCase):
    def test_los_rotulos_dentro_de_un_formulario(self):
        self.assertEqual(datos_de_posgrado(LISTA_DE_DATOS, "Maestría en Ciencia de Datos"), {
            "titulo_otorgado": "Magíster en Ciencia de Datos", "duracion_meses": 24,
            "modalidad": "Presencial"})

    def test_el_titulo_bajo_su_encabezado_y_la_duracion_en_una_tabla(self):
        datos = datos_de_posgrado(ENCABEZADO_Y_TABLA, "Doctorado en Ingeniería Civil")
        self.assertEqual(datos["titulo_otorgado"], "Doctor/a en Ingeniería Civil")
        self.assertEqual(datos["duracion_meses"], 60)

    def test_el_titulo_de_otro_programa_no_es_el_suyo(self):
        self.assertIsNone(datos_de_posgrado(LISTA_DE_DATOS, "Maestría en Estudios Feministas")["titulo_otorgado"])

    def test_la_pagina_que_nombra_el_programa(self):
        self.assertTrue(nombra_el_programa(ENCABEZADO_Y_TABLA, "Doctorado en Ingeniería Civil"))
        self.assertFalse(nombra_el_programa(LISTA_DE_DATOS, "Maestría en Finanzas"))


if __name__ == "__main__":
    unittest.main()
