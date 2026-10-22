import unittest

from rumbo_scraper.parsers import planes_sitios as p


def _pagina(cuerpo: str) -> str:
    return ("<article><p>Carreras de grado</p><p>Tecnicatura</p>"
            f"<h1>Asignaturas de la Tecnicatura</h1>{cuerpo}<p>Facebook</p><p>Estudios sobre Política</p></article>")


class PlanPerioUnlp(unittest.TestCase):
    def test_un_renglon_por_materia_bajo_cada_anio(self):
        html = _pagina("<p>Tramo Inicial</p><p>Taller de introducción</p><h3>Primer Año</h3><p>Historia social</p>"
                       "<p>Primer cuatrimestre</p><p>Periodismo I</p><h3>Segundo Año</h3><p>Periodismo II</p>"
                       "<p>Optativa 1</p><p>Optativa II: Taller A/Seminario B</p>")
        self.assertEqual(p.plan_perio_unlp(html), [("Historia social", 1), ("Periodismo I", 1), ("Periodismo II", 2)])

    def test_un_plan_por_ciclos_no_se_lee(self):
        html = _pagina("<h3>PRIMER CICLO</h3><p>Comunicación popular I</p>")
        self.assertEqual(p.plan_perio_unlp(html), [])

    def test_sin_el_primer_anio_no_es_el_plan(self):
        self.assertEqual(p.plan_perio_unlp(_pagina("<h3>Segundo año</h3><p>Periodismo II</p>")), [])


if __name__ == "__main__":
    unittest.main()
