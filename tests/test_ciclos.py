import unittest

from rumbo_scraper.database.exportar_catalogo import es_un_ciclo


class Ciclos(unittest.TestCase):
    def test_por_el_nombre(self):
        self.assertTrue(es_un_ciclo("CCC Licenciatura en Enfermería"))
        self.assertTrue(es_un_ciclo("Licenciatura en Administración para Contadores Públicos"))
        self.assertTrue(es_un_ciclo("Licenciatura en Redes y Comunicación de Datos para egresados"))
        self.assertTrue(es_un_ciclo("Licenciatura en Actividad Física y Deportes Plan Especial para Profesores"))
        self.assertFalse(es_un_ciclo("Licenciatura en Enfermería"))

    def test_por_su_descripcion(self):
        self.assertTrue(es_un_ciclo("Licenciatura en Historia",
                                    "Este Ciclo de Complementación Curricular le permite al estudiante completar su formación."))
        self.assertTrue(es_un_ciclo("Licenciatura en Gestión Ambiental",
                                    'La carrera se denomina "Licenciatura en Gestión Ambiental - Ciclo de Licenciatura" y el título...'))
        self.assertFalse(es_un_ciclo("Licenciatura en Nutrición",
                                     "Cinco años de cursada. La facultad ofrece además un ciclo de complementación para técnicos."))


if __name__ == "__main__":
    unittest.main()
