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
            ("Duración y título Cuatro cuatrimestres, con un ritmo ideal de tres-cuatro asignaturas", 2),
        ):
            with self.subTest(texto=texto):
                self.assertEqual(duraciones_en(texto), {anios})

    def test_un_numero_suelto_no_es_la_duracion(self):
        self.assertEqual(duraciones_en("Acreditada por 3 años por la CONEAU. 50 años de historia."),
                         set())

    def test_el_titulo_que_pide_el_ingreso_no_es_la_duracion(self):
        # UNTREF's cycles: the applicant's previous degree states its own.
        self.assertEqual(duraciones_en(
            "Duración y título Cuatro cuatrimestres. Condiciones de ingreso: título de profesor "
            "de no menos de cuatro años de duración. Plan de estudios"), {2})
        self.assertEqual(duraciones_en(
            "Duración y título Es una carrera de dos (2) años y medio (5 cuatrimestres) de duración. "
            "Condiciones de ingreso Título de nivel superior correspondiente a una carrera con una "
            "duración mínima de 3 años y 1400 horas. Plan de estudios* Primer cuatrimestre"), {2.5})

    def test_la_duracion_de_cada_ciclo_no_es_la_de_la_carrera(self):
        # UNQ's profesorados.
        self.assertEqual(duraciones_en(
            "La carrera de Profesorado de Historia tiene una duración de 4 ½ años (cuatro y medio), "
            "con una organización curricular en Ciclos de Formación; siendo 3 (tres) los ciclos que "
            "la componen: un Ciclo Introductorio que tiene una duración de un cuatrimestre; un Ciclo "
            "Inicial que se corresponde con la Diplomatura en Ciencias Sociales y un Ciclo Superior, "
            "los que tienen respectivamente una duración de 2 (dos) años."), {4.5})

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

    def test_la_cifra_de_una_tarjeta_sobre_su_rotulo(self):
        self.assertEqual(duraciones_en("Grado Abogacía 6 años Duración 42 Materias"), {6})
        self.assertEqual(duraciones_en("Despachante de Aduana 5 cuatrim. Duración 20 Materias"), {2.5})

    def test_la_cifra_entre_parentesis_repite_la_palabra(self):
        self.assertEqual(duraciones_en("Duración estimada\n3 (tres) años"), {3})

    def test_la_cifra_de_una_ficha_sobre_el_rotulo_anios(self):
        html = "<main><div><div> 5</div><h5>Años</h5></div><div><div> 4400</div><h5>Hs</h5></div></main>"
        self.assertEqual(duracion_de_la_pagina(html), 5)


if __name__ == "__main__":
    unittest.main()
