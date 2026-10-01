import unittest

from rumbo_scraper.database.agregar_carrera import agregar_al_artefacto, leer_pagina


class AgregarCarrera(unittest.TestCase):
    def test_lee_la_carrera_de_su_encabezado(self):
        html = "<html><body><h1>Carrera de Medicina</h1><p>Duración: 6 años</p>" + "x" * 50 + "</body></html>"
        fila = leer_pagina(html, "https://u.edu.ar/medicina")
        self.assertEqual((fila["nombre_carrera"], fila["nivel"]), ("Medicina", "Grado"))

    def test_rechaza_lo_que_no_es_una_carrera(self):
        with self.assertRaises(ValueError):
            leer_pagina("<html><body><h1>Noticias</h1></body></html>", "https://u.edu.ar/n")

    def test_artefacto_de_guia_y_completo(self):
        fila = {"nombre_carrera": "Medicina", "nivel": "Grado"}
        guia = {"datos": {"universidades": [{"nombre_oficial": "U"}], "ofertas": []}}
        self.assertTrue(agregar_al_artefacto(guia, fila, "https://u/m"))
        self.assertEqual(guia["datos"]["ofertas"][0]["url_oficial"], "https://u/m")
        self.assertFalse(agregar_al_artefacto(guia, fila, "https://u/m"))
        completo = {"datos": {"universidades": [{"nombre_oficial": "U"}], "ofertas": [], "carreras": []}}
        self.assertTrue(agregar_al_artefacto(completo, fila, "https://u/m"))
        self.assertEqual(completo["datos"]["carreras"][0]["nombre_carrera"], "Medicina")


if __name__ == "__main__":
    unittest.main()
