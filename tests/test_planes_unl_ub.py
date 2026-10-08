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
