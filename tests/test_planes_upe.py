import unittest

from rumbo_scraper.parsers.planes_sitios import plan_upe_de


def _palabra(x, y, texto, x2=None, y2=None):
    return f'<word xMin="{x}" yMin="{y}" xMax="{x2 or x + 6 * len(texto)}" yMax="{y2 or y + 10}">{texto}</word>'


class PlanUpe(unittest.TestCase):
    def test_nombres_partidos_y_cuatrimestres_entre_reglas(self):
        palabras = [
            _palabra(157, 204, "Asignatura"), _palabra(253, 204, "Horaria"),
            # The terms' labels turned on their side: "Cuatrimestre" above its "1°".
            _palabra(97, 240, "Cuatrimestre", 109, 290), _palabra(97, 292, "1°", 109, 300),
            _palabra(97, 340, "Cuatrimestre", 109, 380), _palabra(97, 382, "2°", 109, 390),
            _palabra(97, 405, "Cuatrimestre", 109, 445), _palabra(97, 447, "3°", 109, 455),
            _palabra(126, 249, "1"), _palabra(142, 239, "Introducción"), _palabra(142, 249, "al"),
            _palabra(160, 249, "Campo"), _palabra(142, 259, "Profesional"), _palabra(265, 249, "32"),
            _palabra(126, 290, "2"), _palabra(142, 290, "Gestión"), _palabra(190, 290, "Logística"),
            _palabra(240, 290, "l"), _palabra(265, 290, "64"),
            _palabra(126, 345, "3"), _palabra(142, 340, "Fundamentos"), _palabra(142, 350, "de"),
            _palabra(160, 350, "Economía"), _palabra(265, 345, "64"),
            _palabra(123, 400, "4"), _palabra(142, 400, "Matemática"), _palabra(265, 400, "64"),
        ]
        cajas = "<page>" + "".join(palabras) + "</page>"
        # The rules: the second term's cell holds row 3 alone, though its label
        # reaches nearer row 4; the rows' own rules stop short of the labels' column.
        reglas = {0: [(235, 38, 559), (330, 93, 559), (310, 117, 559), (395, 93, 559), (470, 38, 559)]}
        self.assertEqual(plan_upe_de(cajas, reglas), [
            ("Introducción al Campo Profesional", 1), ("Gestión Logística I", 1),
            ("Fundamentos de Economía", 1), ("Matemática", 2)])

    def test_sin_las_reglas_de_un_rotulo_no_lee(self):
        cajas = ("<page>" + _palabra(157, 204, "Asignatura") + _palabra(253, 204, "Horaria")
                 + _palabra(97, 240, "1°") + _palabra(110, 240, "Cuatrimestre")
                 + _palabra(126, 249, "1") + _palabra(142, 249, "Matemática") + "</page>")
        self.assertEqual(plan_upe_de(cajas, {0: []}), [])



class PlanUmendozaPagina(unittest.TestCase):
    def test_pestania_del_plan(self):
        from rumbo_scraper.parsers.planes_sitios import plan_umendoza_pagina

        html = """<div class="fl-tabs-panel-content"><p>Presentación de la carrera</p></div>
<div class="fl-tabs-panel-content"><h2>Plan de estudios</h2><p><em>(s) = semestral.</em></p>
<h3>1er Año</h3><p>Derecho Romano (s)<br/>Introducción al Derecho (s) (p)</p>
<h3><strong>2do Año</strong></h3><p><strong>Ciclo de Instrumentación</strong><br/>Derecho Civil – Parte General (a)</p>
<h3>CONDICIÓN FINAL DE EGRESO</h3><p>Trabajo Final de Investigación (a)</p></div>"""
        self.assertEqual(plan_umendoza_pagina(html), [
            ("Derecho Romano", 1), ("Introducción al Derecho", 1), ("Derecho Civil – Parte General", 2)])


if __name__ == "__main__":
    unittest.main()
