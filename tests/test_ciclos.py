import unittest

from rumbo_scraper.database.exportar_catalogo import es_un_ciclo


class Ciclos(unittest.TestCase):
    def test_por_el_nombre(self):
        self.assertTrue(es_un_ciclo("CCC Licenciatura en Enfermería"))
        self.assertTrue(es_un_ciclo("Licenciatura en Administración para Contadores Públicos"))
        self.assertTrue(es_un_ciclo("Licenciatura en Redes y Comunicación de Datos para egresados"))
        self.assertTrue(es_un_ciclo("Licenciatura en Actividad Física y Deportes Plan Especial para Profesores"))
        self.assertTrue(es_un_ciclo("Ciclo de Traductorado Público de Inglés"))
        self.assertFalse(es_un_ciclo("Licenciatura en Enfermería"))

    def test_por_su_pagina(self):
        from rumbo_scraper.database.exportar_catalogo import _SU_PAGINA_DICE_CICLO, la_pagina_dice_ciclo

        self.assertTrue(_SU_PAGINA_DICE_CICLO.search("titulo licenciada o en psicopedagogia duracion 2 anos ciclo de licenciatura requisitos"))
        self.assertTrue(_SU_PAGINA_DICE_CICLO.search("duracion 1 ano y medio ciclo de licenciatura"))
        self.assertFalse(_SU_PAGINA_DICE_CICLO.search("duracion 4 anos ofrece ademas un ciclo de licenciatura"))
        self.assertTrue(_SU_PAGINA_DICE_CICLO.search(
            "licenciatura en logistica integral ciclo de complementacion curricular resolucion ministerial 1388 2017"))
        self.assertTrue(_SU_PAGINA_DICE_CICLO.search(
            "ficha tecnica de la carrera carrera licenciatura en lengua inglesa ciclo de complementacion curricular titulo final"))
        self.assertFalse(la_pagina_dice_ciclo("https://undelta.edu.ar/carreras/#licenciatura-en-agua"))

    def test_por_su_descripcion(self):
        self.assertTrue(es_un_ciclo("Licenciatura en Historia",
                                    "Este Ciclo de Complementación Curricular le permite al estudiante completar su formación."))
        self.assertTrue(es_un_ciclo("Licenciatura en Gestión Ambiental",
                                    'La carrera se denomina "Licenciatura en Gestión Ambiental - Ciclo de Licenciatura" y el título...'))
        self.assertFalse(es_un_ciclo("Licenciatura en Nutrición",
                                     "Cinco años de cursada. La facultad ofrece además un ciclo de complementación para técnicos."))


if __name__ == "__main__":
    unittest.main()
