import unittest

from rumbo_scraper.parsers.planes_sitios import plan_ub, plan_unl


def _caja(x, y, texto):
    palabras = "".join(f"<word>{p}</word>" for p in texto.split())
    return f'<line xMin="{x}" yMin="{y}" xMax="0" yMax="0">{palabras}</line>'


class PlanUnl(unittest.TestCase):
    def test_anios_y_nombres_partidos(self):
        html = """<p class="meta-carreras">plan de estudios</p>
<p><p>PRIMER AÑO<br />•Introducción a la Bibliotecología y Ciencia<br />de la Información<br />•Inglés I</p>
<p>SEGUNDO AÑO<br />•Servicios de Información y Referencia<br />Especializada<br />•Optativa I<br />
•Trabajo Final<br />*Carrera compartida entre FCA y FCV.</p>
<p><a href="#">+ Información en UNLVirtual</a></p></p>"""
        self.assertEqual(plan_unl(html), [
            ("Introducción a la Bibliotecología y Ciencia de la Información", 1), ("Inglés I", 1),
            ("Servicios de Información y Referencia Especializada", 2), ("Trabajo Final", 2)])


class PlanUb(unittest.TestCase):
    def test_columnas_por_anio(self):
        renglones = [_caja(43, 300, "• Universidad de Málaga"), _caja(48, 480, "PRIMER AÑO"),
                     _caja(43, 494, "Primer semestre"), _caja(43, 502, "• Derechos de la Propiedad Industrial e"),
                     _caja(48, 510, "Intelectuales"), _caja(43, 518, "• Materia Optativa de Formación"),
                     _caja(48, 526, "General (MOFG) 1"), _caja(226, 480, "TERCER AÑO"),
                     _caja(220, 494, "• Contratos (P.G.)"), _caja(402, 480, "MATERIAS OPTATIVAS"),
                     _caja(398, 494, "• Ecología")]
        cajas = "<page>" + "".join(renglones) + "</page>"
        self.assertEqual(plan_ub(cajas), [("Derechos de la Propiedad Industrial e Intelectuales", 1),
                                          ("Contratos (P.G.)", 3)])
        orientada = cajas.replace("</page>", _caja(400, 480, "CUARTO AÑO ORIENTACIÓN") + "</page>")
        self.assertEqual(plan_ub(orientada), [])


if __name__ == "__main__":
    unittest.main()


class PlanUaderGestion(unittest.TestCase):
    TEXTO = """Tecnicatura y Licenciatura en Marketing
Plan de Estudio Tecnicatura en Marketing
1º Año
          Principios de
202101                               ANUAL         2              64
          Administración
202104 Trabajo Intelectual           C1            3              48
          Asignatura Optativa del
202329                              C1 ó C2      3               48
          área social
2º Año
202215 Estadística                   A             2              64
Plan de Estudio Licenciatura en Marketing
4º Año
202439 Seminario de Tesis          ANUAL      5               160
"""

    def test_cada_carrera_su_parte(self):
        from rumbo_scraper.parsers.planes_sitios import plan_uader_gestion

        self.assertEqual(plan_uader_gestion(self.TEXTO, "Tecnicatura en Marketing"), [
            ("Principios de Administración", 1), ("Trabajo Intelectual", 1), ("Estadística", 2)])
        self.assertEqual(plan_uader_gestion(self.TEXTO, "Licenciatura en Marketing")[-1], ("Seminario de Tesis", 4))


class PlanUsi(unittest.TestCase):
    def test_hasta_la_siguiente_seccion(self):
        from rumbo_scraper.parsers.planes_sitios import plan_anios_y_renglones as plan_usi

        html = """<div><p>Plan de Estudios</p><p>Duración: 4 años</p><h4>Primer Año</h4><p>Teoría del Derecho</p>
<p>Derecho Romano</p><h4>Segundo Año</h4><p>Contratos</p><p>Electiva I</p><h4>Otros Requisitos</h4>
<p>Examen de inglés o certificación equivalente.</p><p>Director de la Carrera</p></div>"""
        self.assertEqual(plan_usi(html), [("Teoría del Derecho", 1), ("Derecho Romano", 1), ("Contratos", 2)])


class PlanFceUnse(unittest.TestCase):
    def test_bloques_por_anio(self):
        from rumbo_scraper.parsers.planes_sitios import plan_fce_unse

        html = """<div class="fceyt-pe-year"><label class="fceyt-pe-year-toggle">Primer año</label>
<table><tr><th>N.º</th><th>Asignatura</th></tr><tr><td>1</td><td>Análisis Matemático I</td><td>—</td></tr></table></div>
<div class="fceyt-pe-year"><label class="fceyt-pe-year-toggle">Segundo año</label>
<table><tr><td>10</td><td>Física II</td><td>8</td></tr></table></div>
<div class="fceyt-pe-electivas"><table><tr><td>1</td><td>Electiva de Ríos</td></tr></table></div>"""
        self.assertEqual(plan_fce_unse(html), [("Análisis Matemático I", 1), ("Física II", 2)])
