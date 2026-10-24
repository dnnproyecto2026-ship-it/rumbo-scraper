import unittest

from rumbo_scraper.parsers.folleto_usal import plan_del_folleto

CABECERA = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext"


def tsv(lineas: list[tuple]) -> str:
    """Each line as tesseract gives it: (left, top, text[, height]), one
    word after another, every line its own."""
    filas = [CABECERA]
    for numero, (izquierda, arriba, texto, *alto) in enumerate(lineas, start=1):
        x = izquierda
        alto = alto[0] if alto else 20
        for palabra in texto.split():
            filas.append(f"5\t1\t1\t1\t{numero}\t1\t{x}\t{arriba}\t{len(palabra) * 10}\t{alto}\t90\t{palabra}")
            x += len(palabra) * 10 + 10
    return "\n".join(filas)


def folleto(izquierda: list[str], derecha: list[str]) -> str:
    lineas = [(10, 30 * i, t) for i, t in enumerate(izquierda)]
    lineas += [(600, 30 * i, t) for i, t in enumerate(derecha)]
    return tsv(lineas)


PRIMERO = ["PRIMER AÑO", "Arquitectura | A", "Física C", "Plástica y Visión | A", "Matemática A",
           "Filosofía C", "Teología C", "SEGUNDO AÑO", "Arquitectura |! Cc", "Arquitectura lI! ¡e",
           "Plástica |! C", "Visión || C", "Historia y Teoría de la Arquitectura | C",
           "Historia y Teoría de la Arquitectura |! C"]
SEGUNDO = ["TERCER AÑO", "Arquitectura IV €", "Historia y Teoría de la Arquitectura Il €",
           "Seminario de Interpretación y", "Proyecto para el Patrimonio Construido C",
           "Proyecto de Título:", "Arquitectura, Ciudad y Territorio A", "Ética C",
           "A: Anual - C: Cuatrimestral", "Además de las obligaciones académicas, deberás", "Arquitectura"]


class FolletoUsal(unittest.TestCase):
    def setUp(self):
        self.plan = plan_del_folleto(folleto(PRIMERO, SEGUNDO), "Arquitectura")

    def test_las_dos_columnas_no_se_mezclan(self):
        anios = dict(self.plan)
        self.assertEqual(anios["Física"], 1)
        self.assertEqual(anios["Arquitectura IV"], 3)

    def test_los_trazos_son_numerales_romanos(self):
        nombres = [n for n, _ in self.plan]
        self.assertEqual([n for n in nombres if n.startswith("Arquitectura ") and "," not in n],
                         ["Arquitectura I", "Arquitectura II", "Arquitectura III", "Arquitectura IV"])
        # Un trazo perdido ("Il" en tercero, después de I y II) se renumera en orden.
        self.assertIn(("Historia y Teoría de la Arquitectura III", 3), self.plan)
        # Una sola de la serie conserva su número.
        self.assertIn(("Plástica II", 2), self.plan)
        self.assertIn(("Plástica y Visión I", 1), self.plan)

    def test_nombres_partidos_y_titulos_de_grupo(self):
        self.assertIn(("Seminario de Interpretación y Proyecto para el Patrimonio Construido", 3), self.plan)
        self.assertIn(("Proyecto de Título: Arquitectura, Ciudad y Territorio", 3), self.plan)

    def test_la_leyenda_y_el_pie_no_son_materias(self):
        nombres = [n for n, _ in self.plan]
        self.assertNotIn("Arquitectura", nombres)
        self.assertFalse(any("Anual" in n or "deberás" in n for n in nombres))
        self.assertEqual(nombres[-1], "Ética")

    def test_un_folleto_con_restos_del_ocr_no_se_toma(self):
        sucio = SEGUNDO[:3] + ["Programación !l el Teoría de Lenguajes"] + SEGUNDO[3:]
        self.assertEqual(plan_del_folleto(folleto(PRIMERO, sucio), "Arquitectura"), [])

    def test_pocas_materias_no_son_un_plan(self):
        self.assertEqual(plan_del_folleto(folleto(PRIMERO[:4], []), "Arquitectura"), [])


class FolletoActuario(unittest.TestCase):
    """The degree's name drawn large between two years of the left column,
    the duration's letter read as "e]" or "[el", and a capital "É" read
    without its accent (FolletoGradoActuario, FolletoGradoMartillero)."""

    def setUp(self):
        izquierda = [(10, 30 * i, t) for i, t in enumerate(
            ["Primer Año", "Matemática | Cc", "Matemática II [e", "Filosofía e", "Sociología Cc",
             "Teología e]", "Contabilidad [el", "Segundo Año", "Estadística | Cc", "Estadística || e",
             "Electiva | e", "Microeconomía <", "Trabajo Integrador Final - TIF C"])]
        izquierda.append((10, 400, "Actuario", 77))
        derecha = [(600, 30 * i, t) for i, t in enumerate(
            ["Tercer Año", "Electiva |! Cc", "Estadística 111 [e", "Idioma (Optativa 11) €",
             "Cuarto Año", "Etica profesional [el", "Electiva 11 C", "C: Cuatrimestral"])]
        self.plan = plan_del_folleto(tsv(izquierda + derecha), "Actuario")

    def test_el_nombre_del_titulo_no_es_materia(self):
        self.assertNotIn("Actuario", [n for n, _ in self.plan])
        self.assertEqual(len(self.plan), 16)

    def test_restos_de_la_duracion(self):
        self.assertIn(("Teología", 1), self.plan)
        self.assertIn(("Contabilidad", 1), self.plan)
        self.assertIn(("Microeconomía", 2), self.plan)
        self.assertIn(("Trabajo Integrador Final - TIF", 2), self.plan)

    def test_numerales_y_tilde(self):
        self.assertIn(("Electiva III", 4), self.plan)
        self.assertIn(("Estadística III", 3), self.plan)
        self.assertIn(("Idioma (Optativa II)", 3), self.plan)
        self.assertIn(("Ética profesional", 4), self.plan)


if __name__ == "__main__":
    unittest.main()
