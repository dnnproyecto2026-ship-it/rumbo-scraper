"""Tests for the academic unit a career page names."""

import unittest

from rumbo_scraper.parsers.unidad import Unidad, es_la_pagina_de, unidad_de_la_pagina


def pagina(titulo="", migas="", cuerpo="", pie="", h1=""):
    return (f"<html><head><title>{titulo}</title></head><body>"
            f"<nav>Facultad de Derecho | Facultad de Medicina</nav>"
            f"<div class='breadcrumb'>{migas}</div><main><h1>{h1}</h1>{cuerpo}</main>"
            f"<footer>{pie}</footer></body></html>")


class DondeLaPaginaHablaDeSi(unittest.TestCase):
    def test_el_titulo_de_un_sitio_de_facultad(self):
        html = pagina(titulo="Bioquímica - Facultad de Ciencias Exactas y Naturales - UNMdP")
        self.assertEqual(unidad_de_la_pagina(html, []),
                         Unidad("Facultad de Ciencias Exactas y Naturales", "Facultad"))

    def test_la_miga_de_pan_y_la_unidad_ya_publicada(self):
        html = pagina(migas="Inicio > Escuela de Negocios > Licenciatura en Finanzas")
        self.assertEqual(unidad_de_la_pagina(html, ["Negocios", "Derecho"]),
                         Unidad("Negocios", "Escuela"))

    def test_sin_la_universidad_pegada(self):
        html = pagina(titulo="Medicina | Instituto de Ciencias de la Salud de la UNAJ")
        self.assertEqual(unidad_de_la_pagina(html, []).nombre, "Instituto de Ciencias de la Salud")

    def test_dos_unidades_distintas_no_dan_ninguna(self):
        html = pagina(titulo="Facultad de Ingeniería",
                      migas="Inicio > Facultad de Ciencias Económicas")
        self.assertIsNone(unidad_de_la_pagina(html, []))

    def test_el_menu_y_el_pie_no_cuentan(self):
        html = pagina(pie="Facultad de Odontología · Facultad de Psicología")
        self.assertIsNone(unidad_de_la_pagina(html, []))


class ElCuerpoDeLaPagina(unittest.TestCase):
    def test_una_unidad_publicada_nombrada_dos_veces(self):
        html = pagina(cuerpo="<p>La Facultad de Ciencias Sociales dicta la carrera.</p>"
                             "<p>Contacto de la Facultad de Ciencias Sociales</p>")
        self.assertEqual(unidad_de_la_pagina(html, ["Facultad de Ciencias Sociales"]).nombre,
                         "Facultad de Ciencias Sociales")

    def test_una_sola_mencion_no_alcanza(self):
        html = pagina(cuerpo="<p>Convenio con la Facultad de Ingeniería de la UBA</p>")
        self.assertIsNone(unidad_de_la_pagina(html, []))

    def test_una_unidad_de_otra_universidad_no_es_de_esta(self):
        html = pagina(cuerpo="<p>Facultad de Derecho y Ciencias Sociales</p>"
                             "<p>Facultad de Derecho y Ciencias Sociales</p>")
        self.assertIsNone(unidad_de_la_pagina(html, ["Facultad de Arquitectura"]))

    def test_dos_unidades_en_el_cuerpo_no_dan_ninguna(self):
        html = pagina(cuerpo="<p>Departamento de Economía</p><p>Departamento de Economía</p>"
                             "<p>Departamento de Humanidades</p>")
        self.assertIsNone(unidad_de_la_pagina(html, []))


class LaPaginaDeLaCarrera(unittest.TestCase):
    def test_el_titulo_nombra_la_carrera(self):
        self.assertTrue(es_la_pagina_de(pagina(titulo="Licenciatura en Nutrición | UFLO"),
                                        "Licenciatura en Nutrición"))

    def test_una_pagina_de_cursos_no_es_la_de_bioquimica(self):
        self.assertFalse(es_la_pagina_de(pagina(titulo="Escuela de Formación Técnica - Cursos"),
                                         "Bioquímica"))


if __name__ == "__main__":
    unittest.main()
