import unittest

from rumbo_scraper.parsers.folleto_usal import plan_del_folleto

CABECERA = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext"


def tsv(lineas: list[tuple[int, int, str]]) -> str:
    """Each line as tesseract gives it: (left, top, text), one word after
    another, every line its own."""
    filas = [CABECERA]
    for numero, (izquierda, arriba, texto) in enumerate(lineas, start=1):
        x = izquierda
        for palabra in texto.split():
            filas.append(f"5\t1\t1\t1\t{numero}\t1\t{x}\t{arriba}\t{len(palabra) * 10}\t20\t90\t{palabra}")
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


if __name__ == "__main__":
    unittest.main()
