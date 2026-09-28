"""Tests for the degree, duration and modality read off a postgraduate's page."""

import unittest

from rumbo_scraper.parsers.datos_posgrado import datos_de_posgrado, limpio, nombra_el_programa, titulo_mencionado, duracion_mencionada

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

    def test_un_titulo_a_los_gritos_o_cortado(self):
        self.assertEqual(limpio("ESPECIALISTA EN DOCENCIA Y PRODUCCIÓN TEATRAL"),
                         "Especialista en Docencia y Producción Teatral")
        self.assertEqual(limpio("DOCTOR/A DE LA UNRN MENCIÓN ARQUITECTURA"), "Doctor/a de la UNRN Mención Arquitectura")
        self.assertIsNone(limpio("Magister en Gestión del"))
        self.assertEqual(limpio("MAGÍSTER EN DIABETES MELLITUS expedido por la Universidad Favaloro"),
                         "Magíster en Diabetes Mellitus")
        self.assertEqual(limpio("ESPECIALISTA EN ENDODONCIA.: Requisitos a cumplir para recibir el diploma"),
                         "Especialista en Endodoncia")
        self.assertEqual(limpio("Magíster en Aplicaciones de Información Espacial, se despliegan a lo largo"),
                         "Magíster en Aplicaciones de Información Espacial")
        self.assertEqual(limpio("MAGISTER EN NEUROCIENCIAS: Requisitos a cumplir para recibir el diploma"),
                         "Magister en Neurociencias")
        for nombre in ("Especialista en Divulgación de la Ciencia, la Tecnología y la Innovación",
                       "Magíster en Lenguas Extranjeras: Problemáticas Sociodidácticas",
                       "Especialista en Derecho Notarial, Registral e Inmobiliario"):
            self.assertEqual(limpio(nombre), nombre)
        self.assertEqual(limpio("Magíster en Ciencias Sociales, mención Historia"),
                         "Magíster en Ciencias Sociales, mención Historia")

    def test_otras_formas_de_decir_el_titulo(self):
        for html in ("<main><p>Título con reconocimiento oficial y validez nacional que otorga:</p>"
                     "<p>Magíster en Derecho Empresario</p></main>",
                     "<main><p>GRADO OTORGADO:</p><p>Magíster en Derecho Empresario</p></main>",
                     "<main><p>La Dirección General otorga validez al título de Magíster en Derecho "
                     "Empresario.</p></main>"):
            self.assertEqual(datos_de_posgrado(html, "Maestría en Derecho Empresario")["titulo_otorgado"],
                             "Magíster en Derecho Empresario")

    def test_el_titulo_que_encabeza_un_documento(self):
        self.assertEqual(titulo_mencionado(["Plan de estudios", "MAGÍSTER EN DERECHO DEL TRABAJO", "Asignatura 1"],
                                           "Maestría en Derecho del Trabajo"), "Magíster en Derecho del Trabajo")
        self.assertEqual(titulo_mencionado(["otorga el título de Doctor/a en Ingeniería."], "Doctorado en Ingeniería"),
                         "Doctor/a en Ingeniería")

    def test_un_titulo_de_otro_tipo_u_otro_tema_no_es_el_suyo(self):
        self.assertIsNone(titulo_mencionado(["Especialista en Estudios Latinoamericanos"],
                                            "Maestría en Estudios Latinoamericanos"))
        self.assertIsNone(titulo_mencionado(["Magíster en Ingeniería Química"], "Maestría en Ingeniería"))

    def test_la_duracion_dicha_en_una_frase(self):
        for linea, meses in (("La carrera tiene una duración de dos años.", 24),
                             ("Cuatro cuatrimestres de duración, con cursado virtual.", 24),
                             ("Se cursa en 18 meses.", 18),
                             ("Duración total: 3 (tres) años", 36)):
            self.assertEqual(duracion_mencionada([linea], "Maestría en Algo"), meses, linea)

    def test_la_duracion_del_titulo_de_grado_no_es_la_suya(self):
        self.assertIsNone(duracion_mencionada(
            ["Requisito: título de grado universitario de 4 años de duración"], "Maestría en Algo"))
        self.assertIsNone(duracion_mencionada(
            ["La carrera dura dos años de duración.", "Duración: 3 años"], "Maestría en Algo"))
        self.assertIsNone(duracion_mencionada(
            ["Podrán inscribirse graduados con título de grado de",
             "cuatro (4) años de duración como mínimo"], "Maestría en Algo"))

    def test_la_pagina_que_nombra_el_programa(self):
        self.assertTrue(nombra_el_programa(ENCABEZADO_Y_TABLA, "Doctorado en Ingeniería Civil"))
        self.assertFalse(nombra_el_programa(LISTA_DE_DATOS, "Maestría en Finanzas"))


if __name__ == "__main__":
    unittest.main()
