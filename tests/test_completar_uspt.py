import unittest

from rumbo_scraper.database.completar_uspt import duracion_de, titulo_de_la_resolucion


class CompletarUspt(unittest.TestCase):
    def test_duracion_en_sus_formas(self):
        self.assertEqual(duracion_de("4 año/s"), 4)
        self.assertEqual(duracion_de("2 años y medio"), 2.5)
        self.assertEqual(duracion_de("4"), 4)
        self.assertEqual(duracion_de("3 años"), 3)
        self.assertIsNone(duracion_de("1600 horas"))
        self.assertIsNone(duracion_de(None))

    def test_titulo_de_la_resolucion(self):
        texto = ("tiene trámite la solicitud de otorgamiento de reconocimiento oficial y validez nacional para los "
                 "títulos de LICENCIADO/A EN CIENCIA DE DATOS y TÉCNICO/A UNIVERSITARIO/A EN CIENCIA DE DATOS, "
                 "efectuada por la UNIVERSIDAD")
        self.assertEqual(titulo_de_la_resolucion(texto, "Licenciatura en Ciencias de Datos"),
                         "Licenciado/a en Ciencia de Datos")
        texto = "validez nacional para el título de CONTADOR/A PÚBLICO efectuada por la UNIVERSIDAD DE SAN PABLO"
        self.assertEqual(titulo_de_la_resolucion(texto, "Contador Público"), "Contador/a Público")
        self.assertIsNone(titulo_de_la_resolucion("sin la fórmula", "Contador Público"))


if __name__ == "__main__":
    unittest.main()
