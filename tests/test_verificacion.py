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
        # A school of the university on a domain of its own, linked from its home.
        self.assertTrue(v.es_oficial("http://www.ips.edu.ar/wp-content/uploads/2018/05/TUGP.pdf", "https://unr.edu.ar"))
        self.assertFalse(v.es_oficial("http://www.ips.edu.ar/x.pdf", "https://www.unc.edu.ar"))

    def test_la_fuente_dice_la_materia_con_palabras_enteras(self):
        fuente = v.plano("1er año: ANÁLISIS MATEMÁTICO I - Álgebra y Geometría Analítica")
        self.assertTrue(v.dice(fuente, "Análisis Matemático I"))
        self.assertTrue(v.dice(fuente, "Álgebra y geometría analítica"))
        self.assertFalse(v.dice(fuente, "Análisis Matemático II"))
        self.assertFalse(v.dice(fuente, "Matemática"))

    def test_una_palabra_partida_al_final_del_renglon_se_une(self):
        self.assertTrue(v.dice(v.plano("Química de los Alimen- tos"), "Química de los Alimentos"))

    def test_un_nombre_cortado_por_el_fin_de_pagina_se_une(self):
        # UNTREF's annex of the RM 1134/20: the row's name runs on to page 2.
        fuente = v.plano("Seminario de Investigación Geografía IF-2020-36779914-APN-DNGYFU#MECCYT Página 1 de 2 "
                         "Carga Carga Modalidad Cod Asignatura Régimen Horaria Correlativas Obs 167 Integrada "
                         "Cuatrimestral 8 128 Urbana")
        self.assertTrue(v.dice(fuente, "Seminario de Investigación Integrada"))
        self.assertFalse(v.dice(fuente, "Seminario de Investigación Cuantitativa"))
        # Without a page's end between them, the two parts are not one name.
        self.assertFalse(v.dice(v.plano("Seminario de Investigación Geografía 167 Integrada"),
                                "Seminario de Investigación Integrada"))

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

    def test_el_veredicto_sobre_lo_que_el_export_ya_saco_no_se_olvida(self):
        from rumbo_scraper.database.verificar_catalogo import _veredictos_que_siguen

        anterior = {"materias": [
            {"carrera": "Obstetricia", "materia": "norma.htm Ley", "estado": "no_lo_dice"},
            {"carrera": "Agronomía", "materia": "Agroecología CFB", "estado": "verificado",
             "como_la_dice_la_fuente": "Agroecología"},
            {"carrera": "Agronomía", "materia": "Botánica", "estado": "verificado"},
            {"carrera": "Agronomía", "materia": "Química", "estado": "sin_fuente"},
        ]}
        hallado = {"materias": [
            {"carrera": "Agronomía", "materia": "Agroecología", "estado": "verificado"},
            {"carrera": "Agronomía", "materia": "Química", "estado": "verificado"},
        ]}
        self.assertEqual([f["materia"] for f in _veredictos_que_siguen(anterior, hallado)],
                         ["norma.htm Ley", "Agroecología CFB"])

    def test_lo_que_el_plan_no_decia_se_vuelve_a_mirar(self):
        from rumbo_scraper.database.verificar_catalogo import _contradichas_antes

        anterior = {"materias": [
            {"carrera": "Desarrollo Agrario", "materia": "Química general", "estado": "no_lo_dice", "fuente": None},
            {"carrera": "Desarrollo Agrario", "materia": "Biología", "estado": "verificado", "fuente": "x"},
        ]}
        self.assertEqual(_contradichas_antes(anterior), [
            {"nombre_materia": "Química general", "carrera_o_programa": "Desarrollo Agrario"}])
        self.assertEqual(_contradichas_antes(None), [])


class NombreConGuion(unittest.TestCase):
    def test_a_name_broken_at_its_hyphen_is_found(self):
        fuente = v.plano("Producción de Hortalizas Primavero-\nEstivales")
        self.assertTrue(v.dice(fuente, "Producción de Hortalizas Primavero-Estivales"))
        self.assertTrue(v.dice(v.plano("Teoría Socio-Histórica"), "Teoría Socio-Histórica"))

    def test_a_pair_named_at_once_names_each(self):
        fuente = v.plano("Economía Política I y II | Estadística Aplicada I, II y III")
        self.assertTrue(v.dice(fuente, "Economía Política II"))
        self.assertTrue(v.dice(fuente, "Estadística Aplicada III"))
        self.assertFalse(v.dice(v.plano("Economía Política I"), "Economía Política II"))


class NombreConCortes(unittest.TestCase):
    def test_a_long_name_cut_inside_its_words_is_found(self):
        casos = [("Curso de Inglés para Ciencias de la Salud", "curso de ingles para ciencias dela salud"),
                 ("Química Inorgánica Aplicada", "quimica inorg a nica aplicada"),
                 ("Técnicas Kinésicas III", "tecnicas kinesicas i i i"),
                 ("Electrofisiología No Invasiva", "electrofisiologia no lnvasiva")]
        for nombre, fuente in casos:
            self.assertTrue(v.dice(v.plano(fuente), nombre), nombre)

    def test_short_names_and_other_words_are_not_matched(self):
        self.assertFalse(v.dice(v.plano("fisicaii"), "Física II"))
        self.assertFalse(v.dice(v.plano("matematica discretas aplicadas"), "Matemática Discreta Avanzada"))
        self.assertFalse(v.dice(v.plano("introduccion a la biologia celular molecular"), "Introducción a la Biología Molecular"))

    def test_a_closing_roman_numeral_read_as_a_digit_is_found(self):
        # FCQ-UNC's Ord. 6/2018: the scan prints "Física I", its OCR "Física 1".
        fuente = v.plano("Física 1 71 4,7 Laboratorio 1 74 4,8 Procesos biotecnológicos lI 70")
        for nombre in ("Física I", "Laboratorio I", "Procesos biotecnológicos II"):
            self.assertTrue(v.dice(fuente, nombre), nombre)
        self.assertFalse(v.dice(fuente, "Física II"))
        self.assertFalse(v.dice(v.plano("Física 11"), "Física I"))
        self.assertFalse(v.dice(v.plano("Física 2"), "Física II"))


class PlanEnDrive(unittest.TestCase):
    def test_plan_en_drive_enlazado_por_la_pagina(self):
        from rumbo_scraper.database.verificar_catalogo import _planes_enlazados

        html = ('<a href="https://drive.google.com/file/d/AB-1/view">Formulario Inscripción</a>'
                '<a href="https://drive.google.com/file/d/CD_2/view?usp=drive_link">Plan de Estudio</a>')
        self.assertEqual(_planes_enlazados(html, "https://iuymca.edu.ar/profesorado/"),
                         ["https://drive.google.com/uc?export=download&id=CD_2"])


class TextoDeLasImagenes(unittest.TestCase):
    def test_las_imagenes_del_cuerpo_de_una_pagina_corta_se_leen_y_los_logos_no(self):
        from unittest import mock

        from rumbo_scraper.database import verificar_catalogo as vc

        pedidas = []

        class Visitante:
            class client:
                @staticmethod
                def get(direccion):
                    pedidas.append(direccion)
                    return mock.Mock(status_code=200, content=b"x")

        fuentes = mock.Mock(visitante=Visitante)
        html = ('<img src="/sites/default/files/Logo_CienciasMed_0.png">'
                '<img src="/sites/default/files/inline-images/Captura2_1.JPG">'
                '<img src="https://otro.com/plan.png">')
        with mock.patch("rumbo_scraper.parsers.ocr.texto_de_imagen", return_value="SEGUNDO AÑO Anatomía"):
            leido = vc._texto_de_las_imagenes(fuentes, html, "https://www.fmed.uba.ar/plan", "poco texto")
            largo = vc._texto_de_las_imagenes(fuentes, html, "https://www.fmed.uba.ar/plan", "x" * 7000)
        self.assertEqual(pedidas, ["https://www.fmed.uba.ar/sites/default/files/inline-images/Captura2_1.JPG"])
        self.assertIn("Anatomía", leido)
        self.assertEqual(largo, "")


class NumeroPegadoALaPalabra(unittest.TestCase):
    def test_el_numero_de_renglon_pegado_a_la_palabra_es_otro_token(self):
        self.assertEqual(v.plano("4.5Práctica y Residencia"), "4 5 practica y residencia")
        self.assertEqual(v.plano("Física 2"), "fisica 2")


class FuenteDeUnInstitutoSinSitio(unittest.TestCase):
    def test_sin_sitio_propio_vale_el_de_la_autoridad_educativa(self):
        from rumbo_scraper.verificacion import es_oficial
        self.assertTrue(es_oficial("https://abc.gob.ar/secretarias/sites/default/files/x.pdf", None))
        self.assertTrue(es_oficial("https://isfdyt89-bue.infd.edu.ar/sitio/x.pdf", ""))
        self.assertFalse(es_oficial("https://iseta.edu.ar/x.pdf", None))
        self.assertFalse(es_oficial(None, None))
        # With a site of its own, only that site is its source.
        self.assertFalse(es_oficial("https://abc.gob.ar/x.pdf", "https://iseta.edu.ar"))
