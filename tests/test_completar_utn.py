import unittest

from rumbo_scraper.database.completar_utn import duracion_de, titulo_de


class CompletarUtn(unittest.TestCase):
    def test_duracion_en_sus_formas(self):
        self.assertEqual(duracion_de("<p><strong>Años:</strong> 5½</p><p><strong>Horas reloj:</strong> 4182</p>"), 5.5)
        self.assertEqual(duracion_de("La duración de la carrera es de dos (2) años de dos cuatrimestres"), 2)
        self.assertEqual(duracion_de("5 (CINCO) años."), 5)
        self.assertEqual(duracion_de(" 2 años y 1/2 "), 2.5)
        # Hours alone are not a duration.
        self.assertIsNone(duracion_de("<span>1472 hs</span>"))

    def test_titulo_solo_si_es_el_de_la_carrera(self):
        carrera = {"nombre_carreras": "Licenciatura en Comercio Electrónico",
                   "info": 'La carrera se denomina "Licenciatura en Comercio Electrónico - Ciclo de Complementación '
                           'Curricular" y el título que otorga es el de "Licenciado/a en Comercio Electrónico".'}
        self.assertEqual(titulo_de(carrera), "Licenciado/a en Comercio Electrónico")
        # The service's slip: Automatización's degree "en Administración y Control".
        otra = {"nombre_carreras": "Licenciatura en Automatización y Control",
                "info": 'y el título que otorga es el de "Licenciado/a en Administración y Control".'}
        self.assertIsNone(titulo_de(otra))


if __name__ == "__main__":
    unittest.main()
