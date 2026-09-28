import unittest

from rumbo_scraper.parsers.titulo import titulo_de_la_pagina, titulos_en


class Titulo(unittest.TestCase):
    def test_el_rotulo_y_la_frase(self):
        self.assertEqual(titulos_en("Título: Licenciado/a en Economía\nDuración: 5 años"), ["Licenciado/a en Economía"])
        self.assertEqual(titulos_en("Se expide el título de Profesor/a de Lengua Inglesa, con validez nacional."),
                         ["Profesor/a de Lengua Inglesa"])

    def test_lo_que_no_es_un_titulo_no_cuenta(self):
        self.assertEqual(titulos_en("Título: 2 años de cursada"), [])

    def test_solo_la_clase_de_titulo_no_es_un_titulo(self):
        self.assertEqual(titulos_en("Título: Licenciado"), [])

    def test_la_abreviatura_no_corta_el_titulo(self):
        self.assertEqual(titulos_en("Título: Profesor/a en Cs. Biológicas"), ["Profesor/a en Ciencias Biológicas"])

    def test_en_mayusculas_se_escribe_con_tildes(self):
        html = "<main><p>TÍTULO QUE SE OTORGA:</p><p>CONTADOR PUBLICO NACIONAL</p></main>"
        self.assertEqual(titulo_de_la_pagina(html, "Contador Público Nacional"), "Contador Público Nacional")

    def test_de_dos_titulos_el_de_la_carrera(self):
        html = ("<main><p>Título: Licenciado en Química</p>"
                "<p>Título intermedio: Técnico Universitario en Laboratorio</p></main>")
        self.assertEqual(titulo_de_la_pagina(html, "Licenciatura en Química"), "Licenciado en Química")

    def test_rotulo_sin_dos_puntos_en_su_renglon(self):
        html = ("<main><p>Identificación de la carrera:</p><p>Nombre del título a otorgar</p>"
                "<p>Técnico/a Universitario/a en Desarrollo Sostenible</p><p>Nivel Académico</p></main>")
        self.assertEqual(titulo_de_la_pagina(html, "Tecnicatura Universitaria en Desarrollo Sostenible"),
                         "Técnico/a Universitario/a en Desarrollo Sostenible")

    def test_titulo_de_grado_como_rotulo(self):
        html = "<main><p>Ingeniería en Informática</p><p>Título de Grado</p><p>Ingeniero/a en Informática</p><p>5</p></main>"
        self.assertEqual(titulo_de_la_pagina(html, "Ingeniería en Informática"), "Ingeniero/a en Informática")

    def test_sin_el_numero_de_la_seccion_siguiente(self):
        self.assertEqual(titulos_en("Título: Técnico/a Universitario/a en Guía de Turismo 1.3"),
                         ["Técnico/a Universitario/a en Guía de Turismo"])

if __name__ == "__main__":
    unittest.main()
