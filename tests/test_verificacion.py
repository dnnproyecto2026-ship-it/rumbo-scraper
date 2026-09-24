"""Tests for the checks that verify the catalogue against its sources."""

import json
import tempfile
import unittest
from pathlib import Path

from rumbo_scraper import verificacion as v


class VerificacionTest(unittest.TestCase):
    def test_el_dominio_de_una_facultad_es_el_de_su_universidad(self):
        self.assertEqual(v.dominio("https://www.fi.uba.ar/grado/ingenieria"), "uba.ar")
        self.assertEqual(v.dominio("https://economicas.unq.edu.ar/x"), "unq.edu.ar")
        self.assertEqual(v.dominio("https://www.utdt.edu/ver"), "utdt.edu")
        self.assertTrue(v.es_oficial("https://www.fi.uba.ar/plan", "https://www.uba.ar"))
        self.assertFalse(v.es_oficial("https://ar.linkedin.com/in/alguien", "https://www.utdt.edu"))
        self.assertFalse(v.es_oficial("https://www.unla.edu.ar/x", "https://www.unq.edu.ar"))

    def test_la_fuente_dice_la_materia_con_palabras_enteras(self):
        fuente = v.plano("1er año: ANÁLISIS MATEMÁTICO I - Álgebra y Geometría Analítica")
        self.assertTrue(v.dice(fuente, "Análisis Matemático I"))
        self.assertTrue(v.dice(fuente, "Álgebra y geometría analítica"))
        self.assertFalse(v.dice(fuente, "Análisis Matemático II"))
        self.assertFalse(v.dice(fuente, "Matemática"))

    def test_una_palabra_partida_al_final_del_renglon_se_une(self):
        self.assertTrue(v.dice(v.plano("Química de los Alimen- tos"), "Química de los Alimentos"))

    def test_el_texto_incluye_los_datos_de_los_scripts(self):
        html = ('<html><body><h1>Plan</h1><script>{"materia":"Introducci\\u00f3n a la '
                'Programaci\\u00f3n"}</script></body></html>')
        self.assertTrue(v.dice(v.plano(v.texto_de_html(html)), "Introducción a la Programación"))

    def test_la_pagina_de_la_carrera_la_nombra(self):
        pagina = "<html><head><title>Licenciatura en Economía | UNQ</title></head><body></body></html>"
        self.assertTrue(v.nombra_la_carrera(pagina, "Licenciatura en Economía"))
        listado = ("<html><head><title>Carreras de grado</title></head><body><main>"
                   "<p>Abogacía</p><p>Contador Público</p></main></body></html>")
        self.assertFalse(v.nombra_la_carrera(listado, "Licenciatura en Economía"))

    def test_el_perfil_nombra_a_la_persona_en_cualquier_orden(self):
        self.assertTrue(v.nombra_a_la_persona(v.plano("Prof. Rodolfo Gareis - Derecho"), "Gareis, Rodolfo"))
        self.assertFalse(v.nombra_a_la_persona(v.plano("Prof. Rodolfo Pérez"), "Gareis, Rodolfo"))

    def test_la_fuente_que_no_es_oficial_o_no_responde_no_verifica(self):
        sitio = "https://www.itba.edu.ar"
        self.assertEqual(v.estado_de_la_fuente(None, sitio, False), v.SIN_FUENTE)
        self.assertEqual(v.estado_de_la_fuente("https://blog.com/x", sitio, True), v.FUENTE_NO_OFICIAL)
        self.assertEqual(v.estado_de_la_fuente("https://www.itba.edu.ar/x", sitio, False), v.FUENTE_CAIDA)
        self.assertIsNone(v.estado_de_la_fuente("https://www.itba.edu.ar/x", sitio, True))

    def test_la_materia_que_el_plan_hallado_no_dice_no_se_verifica(self):
        fuentes = {"https://u.edu.ar/plan.pdf": v.plano("Física I Física II Química Álgebra")}
        estados = v.materias_del_plan(["Física I", "Física II", "Química", "Quiero inscribirme"], fuentes)
        self.assertEqual(estados["Física I"], (v.VERIFICADO, "https://u.edu.ar/plan.pdf", None))
        self.assertEqual(estados["Quiero inscribirme"], (v.NO_LO_DICE, None, None))

    def test_sin_el_plan_no_se_puede_decir_que_una_materia_falte(self):
        fuentes = {"https://u.edu.ar/carrera": v.plano("Física I es la primera materia")}
        estados = v.materias_del_plan(["Física I", "Física II", "Química", "Álgebra"], fuentes)
        self.assertEqual(estados["Física I"][0], v.VERIFICADO)
        self.assertEqual(estados["Química"], (v.SIN_FUENTE, None, None))

    def test_la_materia_no_sigue_en_la_celda_de_al_lado(self):
        fuente = v.plano("15 | Bases biológicas de la producción animal | Cuatrimestral | CFE")
        self.assertTrue(v.dice(fuente, "Bases biológicas de la producción animal"))
        fuente = v.plano("Producción animal | CFE")
        self.assertFalse(v.dice(fuente, "Producción animal CFE"))

    def test_no_se_exporta_la_materia_que_el_plan_contradice(self):
        from rumbo_scraper.database.exportar_catalogo import materias_contradichas

        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "verificaciones.json"
            ruta.write_text(json.dumps({"universidades": {"Universidad X": {"materias": [
                {"carrera": "Obstetricia", "materia": "norma.htm Ley", "estado": "no_lo_dice"},
                {"carrera": "Obstetricia", "materia": "Anatomía", "estado": "verificado"},
                {"carrera": "Obstetricia", "materia": "Química", "estado": "sin_fuente"},
            ]}}}))
            self.assertEqual(materias_contradichas(ruta),
                             {("Universidad X", "Obstetricia", "norma.htm Ley")})
            self.assertEqual(materias_contradichas(Path(carpeta) / "no_existe.json"), set())

    def test_el_codigo_pegado_se_saca_si_la_fuente_dice_el_nombre_sin_el(self):
        self.assertEqual(v.sin_codigo("Agroecología CFB"), "Agroecología")
        self.assertEqual(v.sin_codigo("Administración de Recursos Humanos I - DC"),
                         "Administración de Recursos Humanos I")
        self.assertIsNone(v.sin_codigo("Física II"))
        fuentes = {"https://u.edu.ar/plan.pdf": v.plano("Agroecología | CFB | Álgebra A")}
        estados = v.materias_del_plan(["Agroecología CFB", "Álgebra A"], fuentes)
        self.assertEqual(estados["Agroecología CFB"],
                         (v.VERIFICADO, "https://u.edu.ar/plan.pdf", "Agroecología"))
        # "Álgebra A" is in the plan as it is: nothing is taken from it.
        self.assertEqual(estados["Álgebra A"], (v.VERIFICADO, "https://u.edu.ar/plan.pdf", None))

    def test_se_exporta_el_nombre_como_lo_dice_el_plan(self):
        from rumbo_scraper.database.exportar_catalogo import materias_corregidas

        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "verificaciones.json"
            ruta.write_text(json.dumps({"universidades": {"Universidad X": {"materias": [
                {"carrera": "Agronomía", "materia": "Agroecología CFB", "estado": "verificado",
                 "como_la_dice_la_fuente": "Agroecología"},
                {"carrera": "Agronomía", "materia": "Botánica", "estado": "verificado"},
            ]}}}))
            self.assertEqual(materias_corregidas(ruta),
                             {("Universidad X", "Agronomía", "Agroecología CFB"): "Agroecología"})
