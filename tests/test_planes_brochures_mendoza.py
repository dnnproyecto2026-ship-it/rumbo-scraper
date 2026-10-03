import unittest

from rumbo_scraper.parsers.planes_sitios import plan_iuas, plan_iuce, plan_iuymca


def _linea(x, y, texto):
    palabras = "".join(f'<word xMin="{x + 40 * i}" yMin="{y}" xMax="1" yMax="1">{p}</word>'
                       for i, p in enumerate(texto.split()))
    return f'<line xMin="{x}" yMin="{y}" xMax="1" yMax="1">{palabras}</line>'


def _pagina(lineas):
    return "<page>" + "".join(_linea(*l) for l in lineas) + "</page>"


class FolletosDeMendoza(unittest.TestCase):
    def test_iuce_columnas_por_anio(self):
        cajas = _pagina([(41, 77, "1° Año"), (268, 77, "2° Año"),
                         (63, 112, "॰Métodos cuantitativos"), (290, 112, "॰Marco legal"),
                         (63, 132, "॰Fundamentos de economía"), (290, 132, "de las organizaciones"),
                         (63, 153, "y finanzas"), (290, 153, "Talleres de aplicación ágil:"),
                         (290, 173, "॰Transporte"), (290, 194, "॰Terrestre y en FFRR"),
                         (728, 181, "Tecnicatura Universitaria"), (63, 500, "॰Sede Ciudad")])
        self.assertEqual(plan_iuce(cajas), [("Métodos cuantitativos", 1), ("Fundamentos de economía y finanzas", 1),
                                            ("Marco legal de las organizaciones", 2),
                                            ("Transporte Terrestre y en FFRR", 2)])

    def test_iuce_sin_primer_anio(self):
        self.assertEqual(plan_iuce(_pagina([(268, 77, "2° Año"), (290, 112, "॰Contabilidad")])), [])

    def test_iuas_palabras_dobles_y_renglon_partido(self):
        dobles = "".join(f'<word xMin="{x}" yMin="150" xMax="1" yMax="1">{t}</word>'
                         for x, t in ((63, "*Química"), (81, "*Química"), (128, "Ambiental"), (146, "Ambiental")))
        cajas = _pagina([(69, 100, "Primer año"), (69, 110, "• Introducción a los Sistemas de Agua y el"),
                         (69, 120, "Saneamiento"), (69, 130, "Segundo año")])
        cajas = cajas.replace("</page>", f"<line>{dobles}</line>"
                              + _linea(69, 160, "¨Hidrología") + _linea(69, 170, "www.iuas.edu.ar") + "</page>")
        self.assertEqual(plan_iuas(cajas), [("Introducción a los Sistemas de Agua y el Saneamiento", 1),
                                            ("Química Ambiental", 2), ("Hidrología", 2)])


    def test_iuymca_numeradas_por_columna(self):
        cajas = _pagina([(60, 50, "Plan de estudio"), (70, 60, "PRIMER AÑO"), (250, 60, "SEGUNDO AÑO"),
                         (40, 70, "01 - Teoría e Historia de"), (240, 70, "03 - Economía II"),
                         (40, 80, "la Actividad Física"), (40, 90, "02 - Informática"),
                         (240, 90, "04 - Idioma II"), (240, 100, "(portugués)"),
                         (40, 120, "Requisitos de ingreso: DNI"), (40, 130, "05 - Otra cosa")])
        self.assertEqual(plan_iuymca(cajas), [("Teoría e Historia de la Actividad Física", 1), ("Informática", 1),
                                              ("Economía II", 2), ("Idioma II (portugués)", 2)])
        salteada = cajas.replace(">04</word>", ">06</word>")
        self.assertEqual(plan_iuymca(salteada), [])


if __name__ == "__main__":
    unittest.main()
