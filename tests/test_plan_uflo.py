import unittest

from rumbo_scraper.parsers.planes_sitios import plan_uflo

HTML = """<div class="gutena-tabs-block"><ul>
<li class="gutena-tab-title" data-tab="1"><div>Primer Año</div></li>
<li class="gutena-tab-title" data-tab="2"><div>Segundo Año</div></li>
<li class="gutena-tab-title" data-tab="3"><div>Espacios Optativos</div></li></ul>
<div class="gutena-tabs-content">
<div class="gutena-tab-block" data-tab="1"><ul><li>Didáctica General.</li><li>Política Educativa.</li></ul></div>
<div class="gutena-tab-block" data-tab="2"><ul><li>Análisis Institucional.</li></ul>
<p><strong>Ciclo de Formación Orientado</strong></p><p>·Orientación en Tecnología Educativa</p>
<ul><li>Tecnologías Emergentes.</li></ul>
<p><strong>Trabajo Final Integrador</strong></p><ul><li>Taller de Trabajo Final Integrador.</li></ul></div>
<div class="gutena-tab-block" data-tab="3"><ul><li>Taller de Gestión de Proyectos.</li></ul></div></div></div>"""


class PlanUflo(unittest.TestCase):
    def test_pestanias_por_anio_sin_orientaciones_ni_optativas(self):
        self.assertEqual(plan_uflo(HTML), [("Didáctica General", 1), ("Política Educativa", 1),
                                           ("Análisis Institucional", 2), ("Taller de Trabajo Final Integrador", 2)])


if __name__ == "__main__":
    unittest.main()
