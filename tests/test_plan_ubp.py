import unittest

from rumbo_scraper.parsers.planes_sitios import plan_ubp

HTML = """<section id="plan"><h2>PLAN DE ESTUDIOS</h2><div class="accordion">
<div class="card"><div class="card-header"><button>PRIMER AÑO</button></div><div class="card-body">
<p><strong>1º Cuatrimestre</strong></p><p>&gt; Matemática I<br/>&gt; Psicoanálisis (D)</p>
<p><strong>2º Cuatrimestre</strong><br/>Semiótica<br/>Psicopatología<br/>(D)</p></div></div>
<div class="card"><div class="card-header"><button>SEGUNDO AÑO</button></div><div class="card-body">
<p><strong>3º Cuatrimestre</strong></p><p>&gt; Física I<br/>…………………………..</p></div></div></div></section>"""


class PlanUbp(unittest.TestCase):
    def test_acordeon_por_anio(self):
        self.assertEqual(plan_ubp(HTML), [("Matemática I", 1), ("Psicoanálisis", 1), ("Semiótica", 1),
                                          ("Psicopatología", 1), ("Física I", 2)])

    def test_sin_seccion(self):
        self.assertEqual(plan_ubp("<html></html>"), [])


if __name__ == "__main__":
    unittest.main()
