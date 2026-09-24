"""Tests for the duration a career page states."""

import unittest

from rumbo_scraper.parsers.duracion import duracion_de_la_pagina, duraciones_en


class Duracion(unittest.TestCase):
    def test_las_formas_en_que_se_escribe(self):
        for texto, anios in (
            ("Duración: 5 años", 5),
            ("La carrera tiene una duración de cuatro años y medio.", 4.5),
            ("Duración estimada: 10 cuatrimestres", 5),
            ("Duración de la carrera: 5 1/2 años", 5.5),
            ("Una carrera de 4 años de duración", 4),
            ("Duración teórica: 3,5 años", 3.5),
            ("DURACIÓN 6 AÑOS", 6),
        ):
            with self.subTest(texto=texto):
                self.assertEqual(duraciones_en(texto), {anios})

    def test_un_numero_suelto_no_es_la_duracion(self):
        self.assertEqual(duraciones_en("Acreditada por 3 años por la CONEAU. 50 años de historia."),
                         set())

    def test_fuera_de_rango_no_es_una_duracion(self):
        self.assertEqual(duraciones_en("Duración: 1 año"), set())
        self.assertEqual(duraciones_en("Duración: 12 años"), set())

    def test_dos_duraciones_en_la_pagina_no_dan_ninguna(self):
        html = ("<main><p>Duración: 5 años.</p>"
                "<p>Título intermedio: duración de 3 años.</p></main>")
        self.assertIsNone(duracion_de_la_pagina(html))

    def test_el_menu_y_el_pie_no_cuentan(self):
        html = ("<nav>Otra carrera · Duración: 3 años</nav>"
                "<main><p>Duración: 5 años</p></main><footer>Duración: 2 años</footer>")
        self.assertEqual(duracion_de_la_pagina(html), 5)


if __name__ == "__main__":
    unittest.main()
