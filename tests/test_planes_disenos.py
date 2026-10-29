import unittest

from rumbo_scraper.database.planes_disenos import _mismo_nombre


class MismoNombre(unittest.TestCase):
    def test_la_tecnicatura_se_llama_como_la_carrera(self):
        self.assertTrue(_mismo_nombre("Enfermería", "Tecnicatura Superior en Enfermería"))
        self.assertTrue(_mismo_nombre("Tecnicatura en Enfermería", "Tecnicatura Superior en Enfermería"))
        self.assertTrue(_mismo_nombre("Profesorado en Educación Primaria", "Profesorado de Educación Primaria"))

    def test_otra_carrera_no(self):
        self.assertFalse(_mismo_nombre("Enfermería", "Tecnicatura Superior en Radiología"))
        self.assertFalse(_mismo_nombre("Profesorado de Educación Primaria", "Educación Primaria"))
