import unittest

from rumbo_scraper.database.completar_dngu import anios, campo, hallar, misma_clase, titulo_limpio


class CompletarDngu(unittest.TestCase):
    def test_anios(self):
        self.assertEqual(anios("6 Años"), 6)
        self.assertEqual(anios("9 Cuatrimestres"), 4.5)
        self.assertEqual(anios("18 Meses"), 1.5)
        self.assertEqual(anios("2.5 Años"), 2.5)
        self.assertIsNone(anios("Consulte"))

    def test_campo_y_clase(self):
        self.assertEqual(campo("Medicina"), campo("Médico"))
        self.assertEqual(campo("Ingeniería Química"), campo("Ingeniero Químico"))
        self.assertNotEqual(campo("Licenciatura en Lengua y Literatura Italianas"),
                            campo("Licenciado/a en Lengua y Literatura Inglesas"))
        self.assertFalse(misma_clase("Enfermero/a", "Licenciatura en Enfermería"))
        self.assertFalse(misma_clase("Licenciado/a en Sistemas", "Analista de Sistemas"))
        self.assertTrue(misma_clase("Técnico Universitario en Logística", "Tecnicatura Universitaria en Logística"))

    def test_titulo_limpio(self):
        self.assertEqual(titulo_limpio("Licenciado/a en Gestión Cultural- MD"), "Licenciado/a en Gestión Cultural")
        self.assertEqual(titulo_limpio("Abogado (Plan 2017)"), "Abogado")

    def test_hallar(self):
        filas = [{"titulo": "Médico", "duracion": "6 Años"}, {"titulo": "Médico", "duracion": "6 Años"},
                 {"titulo": "Licenciado en Enfermería", "duracion": "5 Años"}]
        self.assertEqual(hallar({"nombre_carrera": "Medicina"}, filas), {"titulo": "Médico", "duracion": 6})
        dos = filas + [{"titulo": "Médico", "duracion": "7 Años"}]
        self.assertEqual(hallar({"nombre_carrera": "Medicina"}, dos), {"titulo": "Médico", "duracion": None})
        uba = [{"titulo": "Médico", "duracion": "6.5 Años"}, {"titulo": "Médico/a", "duracion": "6.5 Años"}]
        self.assertEqual(hallar({"nombre_carrera": "Medicina"}, uba), {"titulo": "Médico/a", "duracion": 6.5})
        self.assertIsNone(hallar({"nombre_carrera": "Medicina", "titulo_otorgado": "Médico/a",
                                  "duracion_anios": 6}, filas))


if __name__ == "__main__":
    unittest.main()
