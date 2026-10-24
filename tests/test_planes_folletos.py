import unittest

from rumbo_scraper.database.planes_folletos import con_tilde


class ConTildeTest(unittest.TestCase):
    def test_gives_back_the_accent_the_brochure_reads(self):
        cargadas = [{"nombre_materia": "Etica Profesional", "anio_cursada": 4},
                    {"nombre_materia": "Etica", "anio_cursada": 2},
                    {"nombre_materia": "Estadística", "anio_cursada": 1}]
        leidas = [("Ética Profesional", 4), ("Ética", 3), ("Estadística", 1)]
        self.assertEqual(con_tilde(cargadas, leidas), [(cargadas[0], "Ética Profesional")])

    def test_leaves_a_name_today_reading_does_not_have(self):
        self.assertEqual(con_tilde([{"nombre_materia": "Etica", "anio_cursada": 2}], []), [])


if __name__ == "__main__":
    unittest.main()
