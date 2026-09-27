import unittest

from rumbo_scraper.parsers import planes_sitios as p


class PlanesSitios(unittest.TestCase):
    def test_upc_un_acordeon_por_anio(self):
        html = """<div class="jet-accordion__item"><span class="jet-toggle__label-text">Primer Año</span>
        <div class="jet-toggle__content"><ul><li>Pedagogía</li><li>Optativa 1</li></ul></div></div>
        <div class="jet-accordion__item"><span class="jet-toggle__label-text">Segundo año</span>
        <div class="jet-toggle__content"><ul><li>Danza clásica\xa02</li></ul></div></div>"""
        self.assertEqual(p.plan_upc(html), [("Pedagogía", 1), ("Danza clásica 2", 2)])

    def test_uns_corta_en_las_optativas(self):
        html = """<table><tr><td>PRIMER AÑO</td></tr></table>
        <table><tr><td>9001 INTRODUCCION AL DERECHO</td><td>64hs.</td><td></td></tr></table>
        <table><tr><td>MATERIAS OPTATIVAS</td></tr></table>
        <table><tr><td>9500 DERECHO ROMANO</td><td>64hs.</td></tr></table>"""
        self.assertEqual([a for _, a in p.plan_uns(html)], [1])

    def test_un_plan_sin_primer_anio_no_es_el_plan(self):
        html = """<div class="jet-accordion__item"><span class="jet-toggle__label-text">Segundo año</span>
        <div class="jet-toggle__content"><ul><li>Historia</li></ul></div></div>"""
        self.assertEqual(p.plan_upc(html), [])

    def test_una_regla_no_es_una_materia(self):
        materias = []
        p._agregar(materias, "El alumno debe aprobar 2 (dos) asignaturas electivas", 5)
        p._agregar(materias, "Optativa II", 5)
        self.assertEqual(materias, [])

    def test_unsa_exactas_lee_la_tabla_por_anio(self):
        html = """<table class="exa-plan-table"><tr class="exa-plan-yrow"><td colspan="6">Primer año</td></tr>
        <tr><td class="exa-plan-tcod">1</td><td class="exa-plan-tname">Taller Informático</td><td>I</td></tr>
        <tr class="exa-plan-yrow"><td colspan="6">Segundo año</td></tr>
        <tr><td class="exa-plan-tcod">6</td><td class="exa-plan-tname">Programación</td><td>I</td></tr></table>"""
        self.assertEqual(p.plan_exa_unsa(html), [("Taller Informático", 1), ("Programación", 2)])

    def test_unsa_naturales_deja_el_contacto_y_las_optativas(self):
        html = """<table><tr><td>N°</td><td>Asignatura</td><td>Contacto</td><td>Régimen</td></tr>
        <tr><td>Primer Año</td></tr>
        <tr><td>1</td><td>Botánica</td><td>✉ Dra. Carla Gómez</td><td>II</td></tr>
        <tr><td>PRIMER AÑO</td><td>Matemáticas</td><td>I</td></tr>
        <tr><td>OPTATIVAS</td></tr>
        <tr><td>32</td><td>Anatomía Comparada</td><td>✉ Dr. Fernando Lobo</td><td>II</td></tr></table>"""
        self.assertEqual(p.plan_natura_unsa(html), [("Botánica", 1), ("Matemáticas", 1)])

    def test_unsa_economicas_quita_las_sedes(self):
        html = """<table><tr><td></td><td></td><td>Primer Año</td><td>588</td></tr>
        <tr><td>101</td><td>TP</td><td>Introducción a la Contabilidad - Sede Central - Sede Norte</td><td>56</td></tr>
        <tr><td></td><td></td><td>Economia II - Catedra paralela - Sede Central</td><td></td></tr>
        <tr><td>132</td><td>TP</td><td>Optativa</td><td>56</td></tr></table>"""
        self.assertEqual(p.plan_eco_unsa(html), [("Introducción a la Contabilidad", 1)])

    def test_unsa_ingenieria_termina_en_los_requisitos(self):
        html = """<table><tr><td>PRIMER AÑO</td></tr>
        <tr><td>1</td><td>I</td><td>Análisis Matemático I</td><td>Ciencias Básicas</td></tr>
        <tr><td>2</td><td>I</td><td>Electiva</td><td>Tecnologías Aplicadas</td></tr>
        <tr><td>REQUISITOS CURRICULARES</td></tr>
        <tr><td>39</td><td></td><td>Inglés I</td><td>Complementarias</td></tr></table>"""
        self.assertEqual(p.plan_ing_unsa(html), [("Análisis Matemático I", 1)])

    def test_filas_numeradas_por_anio(self):
        html = """<table><tr><td>Espacio curricular</td><td>Programa</td></tr>
        <tr><td>Primer año</td></tr>
        <tr><td>1. Introducción a la Filosofía</td><td>Descargar</td></tr>
        <tr><td>Segundo año</td></tr>
        <tr><td>9. Didáctica General</td><td>Descargar</td></tr>
        <tr><td>Optativas</td></tr>
        <tr><td>40. Latín</td><td>Descargar</td></tr></table>"""
        self.assertEqual(p.plan_filas_numeradas(html), [("Introducción a la Filosofía", 1), ("Didáctica General", 2)])


if __name__ == "__main__":
    unittest.main()
