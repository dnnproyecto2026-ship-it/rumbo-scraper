import unittest
from unittest import mock

from rumbo_scraper.database.planes_documentos import _nombra, _parece_el_plan_entero
from rumbo_scraper.parsers.planes_sitios import plan_folleto_columnas


def _palabras(lineas):
    palabras = []
    for x, top, texto in lineas:
        for i, p in enumerate(texto.split()):
            palabras.append({"text": p, "x0": x + 30 * i, "x1": x + 30 * i + 25,
                             "top": top, "bottom": top + 7, "upright": True})
    return palabras


class _Pdf:
    def __init__(self, palabras):
        pagina = mock.Mock(width=600, height=800)
        pagina.extract_words.return_value = palabras
        self.pages = [pagina]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _leer(lineas):
    with mock.patch("pdfplumber.open", return_value=_Pdf(_palabras(lineas))):
        return plan_folleto_columnas("folleto.pdf")


class FolletoDeAustral(unittest.TestCase):
    def test_renglon_pegado_sigue_el_nombre(self):
        # Psicología: a wrapped name's second line is 8 points under the
        # first, the next subject 10.
        lineas = [(40, 50, "1º AÑO"), (40, 62, "Sociología"), (40, 72, "Teología I"),
                  (40, 82, "Metodología de la Investigación"), (40, 90, "Cuantitativa"),
                  (40, 100, "Psicometría"), (40, 110, "Psicología Social"),
                  (300, 50, "2º AÑO"), (300, 62, "Ética"), (300, 72, "Bioética")]
        self.assertEqual(_leer(lineas), [("Sociología", 1), ("Teología I", 1),
                                         ("Metodología de la Investigación Cuantitativa", 1),
                                         ("Psicometría", 1), ("Psicología Social", 1),
                                         ("Ética", 2), ("Bioética", 2)])

    def test_optativa_y_la_nota_debajo_no_son_materias(self):
        # Marketing & Management: "Optativa" closes the fourth year and the
        # references' sentence runs under it, opening in lower case.
        lineas = [(40, 50, "1º AÑO"), (40, 62, "Costos"), (40, 82, "Doctrina social"),
                  (40, 102, "Teología II"), (40, 122, "Ética"), (40, 142, "Optativa"),
                  (60, 200, "y adaptarse según las demandas del contexto")]
        self.assertEqual(_leer(lineas), [("Costos", 1), ("Doctrina social", 1),
                                         ("Teología II", 1), ("Ética", 1)])


class NombreCortado(unittest.TestCase):
    def test_coma_o_parentesis_abierto_al_final(self):
        plan = [(f"Materia {n}", 1 + n // 10) for n in range(30)]
        self.assertTrue(_parece_el_plan_entero("Ciencia Política", plan, 4))
        self.assertFalse(_parece_el_plan_entero(
            "Ciencia Política", plan + [("Algunas materias optativas: Management Político,", 3)], 4))
        self.assertFalse(_parece_el_plan_entero(
            "Ciencia Política", plan + [("Naturales y muchas más (la oferta se renueva cada", 3)], 4))


class LaHojaNombraLaCarrera(unittest.TestCase):
    def test_el_titulo_nombra_el_traductorado(self):
        hoja = "PLAN DE ESTUDIO CARRERA (109) TRADUCTOR PÚBLICO EN INGLÉS MODALIDAD PRESENCIAL"
        self.assertTrue(_nombra(hoja, "Traductorado Público en Inglés"))
        self.assertFalse(_nombra(hoja, "Traductorado Público en Francés"))
        self.assertFalse(_nombra("PLAN DE ESTUDIO PROFESORADO EN INGLÉS", "Traductorado Público en Inglés"))


if __name__ == "__main__":
    unittest.main()
