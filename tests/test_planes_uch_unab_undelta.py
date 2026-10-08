import unittest

from rumbo_scraper.parsers.planes_sitios import plan_uch, plan_unab, plan_undelta


def _caja(x, y, texto):
    palabras = "".join(f"<word>{p}</word>" for p in texto.split())
    return f'<line xMin="{x}" yMin="{y}" xMax="0" yMax="0">{palabras}</line>'


class PlanUch(unittest.TestCase):
    TEXTO = """
         Cód. Asignatura                                  Correlativas     Cursado        Carácter
         Primer Semestre
          1    Derecho Privado Parte General                   -         Cuatrimestral   Promocional
1° AÑO
          2    Filosofía y Ética                               -         Cuatrimestral   Promocional
         Segundo Semestre
          3    Derecho Internacional Público y de la           -         Cuatrimestral   Promocional
               Integración
          4    Práctica Profesional Situada       Todos los espacios     Anual           Promocional
                                                      curriculares
         Primer Semestre
2° AÑO
          5    Tecnología Gráﬁca                               -         Cuatrimestral   Promocional
          6    Optativa I:                                     -         Cuatrimestral   Promocional
               Derecho Notarial
"""

    def test_anio_por_los_terminos(self):
        self.assertEqual(plan_uch(self.TEXTO), [
            ("Derecho Privado Parte General", 1), ("Filosofía y Ética", 1),
            ("Derecho Internacional Público y de la Integración", 1),
            ("Práctica Profesional Situada", 1), ("Tecnología Gráfica", 2)])

    def test_numeros_repetidos_o_letras_rotas(self):
        self.assertEqual(plan_uch(self.TEXTO + "          1    Inglés III      11     Anual\n"), [])
        self.assertEqual(plan_uch(self.TEXTO.replace("Filosofía", "Filoso�ía")), [])


class PlanUnab(unittest.TestCase):
    def test_columnas_y_anios(self):
        renglones = [_caja(61, 100, "01. Taller de Ciencia"), _caja(76, 120, "Herramientas computacionales y"),
                     _caja(61, 124, "02. para la ingeniería"), _caja(63, 140, "TOTAL CUATRIMESTRE"),
                     _caja(61, 160, "03. Práctica supervisada (1° cuatr. asignatura anual)"),
                     _caja(63, 180, "TOTAL ANUAL"), _caja(61, 200, "04. Robótica"),
                     _caja(61, 220, "05. Práctica supervisada (2° cuatr. asignatura anual)"),
                     _caja(63, 240, "TOTAL ANUAL"), _caja(63, 260, "CARGA HORARIA TOTAL")]
        cajas = "<page>" + "".join(renglones) + "</page>"
        self.assertEqual(plan_unab(cajas), [
            ("Taller de Ciencia", 1), ("Herramientas computacionales y para la ingeniería", 1),
            ("Práctica supervisada", 1), ("Robótica", 2), ("Práctica supervisada", 2)])


class PlanUndelta(unittest.TestCase):
    def test_listas_por_campo(self):
        texto = """El CFC comprende las siguientes asignaturas:

Inglés Il

Tendencias Globales en el Uso del Agua, Innovación y Nuevos

Negocios del Agua

Electiva I

Campo de Formación Profesional (CPP)
Contenidos mínimos
INGLÉS II
Lectura de textos técnicos.
Tendencias Globales en el Uso del Agua, Innovación y Nuevos Negocios del
Agua
"""
        self.assertEqual(plan_undelta(texto), [
            ("Inglés II", None), ("Tendencias Globales en el Uso del Agua, Innovación y Nuevos Negocios del Agua", None)])
        self.assertEqual(plan_undelta(texto.replace("Inglés Il", "Introducción al Derech  o")), [])


if __name__ == "__main__":
    unittest.main()
