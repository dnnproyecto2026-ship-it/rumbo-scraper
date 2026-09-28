import unittest

from rumbo_scraper.database.completar_titulos import es_de_la_carrera


class EsDeLaCarrera(unittest.TestCase):
    def test_el_titulo_con_campo_comparte_la_raiz_de_la_carrera(self):
        self.assertFalse(es_de_la_carrera("Licenciado/a en Corretaje Inmobiliario", "Derecho"))
        self.assertFalse(es_de_la_carrera("Técnico Universitario en Sonorización", "Licenciatura en Diseño de Sonido"))
        self.assertTrue(es_de_la_carrera("Técnico/a Universitario/a en Emergencias Médicas",
                                         "Tecnicatura Universitaria en Emergencia Médica"))
        self.assertTrue(es_de_la_carrera("Abogado", "Abogacía"))
        self.assertTrue(es_de_la_carrera("Ingeniero Agrimensor", "Agrimensura"))


if __name__ == "__main__":
    unittest.main()
