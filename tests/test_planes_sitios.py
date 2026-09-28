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

    def test_unlz_derecho_un_pliegue_por_anio(self):
        html = """<details class="cr-year"><summary>Primer año</summary><div>
        <p class="cr-materia"><b>1.</b> Introducción al Derecho <span>· 48 hs</span></p></div></details>
        <details class="cr-year"><summary>Segundo año</summary><div>
        <p class="cr-materia"><b>7.</b> Derecho Civil I <span>· 64 hs</span></p></div></details>"""
        self.assertEqual(p.plan_cr_year(html), [("Introducción al Derecho", 1), ("Derecho Civil I", 2)])

    def test_unam_humanidades_anio_y_su_lista(self):
        html = """<table><tr><td>PRIMER AÑO</td></tr><tr><td><ul><li>Introducción a la Historia.</li></ul></td></tr>
        <tr><td>SEGUNDO AÑO</td></tr><tr><td><ul><li>Economía.</li><li>Asignatura Optativa.</li></ul></td></tr></table>"""
        self.assertEqual(p.plan_anio_y_lista(html), [("Introducción a la Historia", 1), ("Economía", 2)])

    def test_unam_economicas_el_plan_mas_nuevo(self):
        html = """<div class="elementor-tab-title">Plan de estudios 2008</div>
        <div><p>Primer Año</p><p>Contabilidad I</p><p>CP101</p></div>
        <div class="elementor-tab-title">Plan de estudios 2020</div>
        <div><p>Primer Año</p><p>Álgebra</p><p>CR103</p><p>Crédito para Optativas</p><p>CR509</p>
        <p>Requisitos extracurriculares</p><p>Idioma Inglés</p><p>CR810</p></div>"""
        self.assertEqual(p.plan_fce_unam(html), [("Álgebra", 1)])

    def test_unam_ingenieria_lee_el_pdf_por_codigo(self):
        texto = """PRIMER AÑO
     CI111          ANUAL           ÁLGEBRA Y GEOMETRÍA ANALÍTICA          -
                     1ºC
     IC411                        SISTEMAS DIGITALES
TERCER AÑO
     CI213           1º C.       PROBABILIDAD Y ESTADÍSTICA 1           CI211
                                                          IC412      IC422"""
        self.assertEqual(p._plan_fio_unam(texto), [("Álgebra y Geometría Analítica", 1),
                                                   ("Sistemas Digitales", 1), ("Probabilidad y Estadística 1", 3)])

    def test_unam_ingenieria_sin_el_nombre_en_su_fila_no_se_lee(self):
        texto = """PRIMER AÑO
     EM211           1º C.       EM111-EM112          -"""
        self.assertEqual(p._plan_fio_unam(texto), [])

    def test_unq_los_nucleos_obligatorios_con_su_cuenta(self):
        html = """<table><tr><td>Núcleo Básico Obligatorio: 2 asignaturas</td><td></td></tr>
        <tr><td>Contabilidad I Básica</td><td>A distancia</td></tr><tr><td>Matemáticas</td><td>A distancia</td></tr>
        <tr><td>Núcleo Profesional Electivo: 1 Asignaturas</td><td></td></tr>
        <tr><td>Impuestos I</td><td>A distancia</td></tr></table>"""
        self.assertEqual(p.plan_unq(html), [("Contabilidad I Básica", None), ("Matemáticas", None)])
        # A núcleo whose rows are not the number it says is not read.
        self.assertEqual(p.plan_unq(html.replace("2 asignaturas", "3 asignaturas")), [])

    def test_unc_lenguas_titulo_y_lista(self):
        html = """<p><b>Ciclo de nivelación</b></p><ul><li>Lengua Castellana</li></ul>
        <p><b>Primer año</b></p><ul><li>Lengua Inglesa I: <a>Cátedra A</a> - <a>Cátedra B</a></li>
        <li><a>Lengua y Cultura Latina I</a> (Optativa)</li><li>Práctica Gramatical</li></ul>"""
        self.assertEqual(p.plan_titulo_y_lista(html), [("Lengua Inglesa I", 1), ("Práctica Gramatical", 1)])

    def test_titulo_y_lista_con_cuatrimestres_dentro_del_anio(self):
        html = """<p><strong>PRIMER AÑO</strong></p><p><em><strong>Primer Cuatrimestre</strong></em></p>
        <ul><li>Introducción al Cálculo</li></ul><p><em><strong>Segundo Cuatrimestre</strong></em></p>
        <ul><li>Álgebra Lineal</li></ul>"""
        self.assertEqual(p.plan_titulo_y_lista(html), [("Introducción al Cálculo", 1), ("Álgebra Lineal", 1)])

    def test_unrc_humanas_solo_obligatorias_del_primer_plan(self):
        html = """<table><tr><th colspan="3">Primer año</th></tr>
        <tr><td>ECONOMÍA I</td><td>Anual</td><td>OBLIGATORIA</td></tr>
        <tr><td>ALEMÁN NIVEL I</td><td>Anual</td><td>OPTATIVA</td></tr></table>
        <table><tr><th colspan="3">Primer año</th></tr><tr><td>PLAN VIEJO</td><td>Anual</td><td>OBLIGATORIA</td></tr></table>"""
        self.assertEqual(p.plan_obligatorias(html), [("Economía I", 1)])

    def test_ucasal_folleto_cuenta_los_anios_y_salta_el_encabezado(self):
        texto = """                  PLAN DE ESTUDIO
                  CARRERA (46) LICENCIATURA
                                  EN CRIMINALÍSTICA
  AÑO
ANUAL     ANÁLISIS MATEMÁTICO I
1° SEM.   FILOSOFÍA
          PRUEBA DE SUFICIENCIA DE IDIOMA INGLES
     0387 426 8800   informes@ucasal.edu.ar    ucasal.edu.ar
                  PLAN DE ESTUDIO
                                  EN CRIMINALÍSTICA
  AÑO
2° SEM.   DERECHO PROCESAL PENAL
4 AÑO
ANUAL     QUÍMICA LEGAL"""
        self.assertEqual(p.plan_ucasal(texto), [])  # the fourth year follows the second
        self.assertEqual(p.plan_ucasal(texto.replace("4 AÑO", "  AÑO")),
                         [("Análisis Matemático I", 1), ("Filosofía", 1), ("Derecho Procesal Penal", 2),
                          ("Química Legal", 3)])

    def test_ucasal_nombres_abreviados_o_cortados_no_se_leen(self):
        self.assertEqual(p.plan_ucasal("  AÑO\n1° SEM.   Dº PROC CIVIL I\n          FILOSOFÍA"), [])
        self.assertEqual(p.plan_ucasal("CORRELATIVIDADES DETALLADAS\n 1 ° Año\n05 0000    FILOSOFIA   3   1 Sem."), [])

    def test_anexo_con_codigo_de_anio_y_nombre_partido(self):
        texto = """                                              PRIMER AÑO
Código   Asignatura                 Régimen         Horas
1.1      Anatomía                   Anual           6           180
1.3.1    Química Estomatológica     Cuatrimestral   6           96
         Básica y Aplicada
         Subtotales                                 35          728
2.7      Fisiología                 Anual           4           120     60          -           1.1. a 1.6.2."""
        self.assertEqual(p.plan_por_codigo_en_texto(texto),
                         [("Anatomía", 1), ("Química Estomatológica Básica y Aplicada", 1), ("Fisiología", 2)])

    def test_la_publicidad_de_la_pagina_termina_el_plan(self):
        html = """<div class="entry-content"><p>Plan de estudios</p><p>PRIMER AÑO</p><p>Derecho Político</p>
        <p>Para finalizar la carrera, vas a necesitar</p><p>Completar los talleres obligatorios</p>
        <p>¿Por qué estudiar Abogacía?</p></div>"""
        self.assertEqual(p._plan_upso(html), [("Derecho Político", 1)])
        html = "<p>Plan de estudios</p><p>1º año</p><p>Historia de Roma</p><p>¿Por qué UMAI?</p><p>Otra cosa</p>"
        self.assertEqual(p._plan_texto_por_anio(html), [("Historia de Roma", 1)])

    def test_sin_marcas_codigos_ni_datos_del_plan(self):
        html = """<p><strong>Primer año</strong></p><ul><li>› Nutrición</li><li>COD: 101 - Guión</li>
        <li>TÍTULO DE PREGRADO: Intérprete</li><li>CARGA HORARIA TOTAL: 2008 horas</li></ul>"""
        self.assertEqual(p.plan_titulo_y_lista(html), [("Nutrición", 1), ("Guión", 1)])

    def test_unnoba_sin_las_opciones_de_una_optativa(self):
        html = """<h2>1º Año</h2><h3>1er Cuatrimestre</h3><button class="subject"><p>Física I (00131)</p></button>
        <h2>2º Año</h2><button class="subject"><p>Lengua Extranjera (GE076)</p></button>
        <dialog><h5>Posibles:</h5><button class="subject"><p>Inglés Técnico (01325)</p></button></dialog>
        <button class="subject"><p>Física II (01295)</p></button>"""
        self.assertEqual(p.plan_unnoba(html), [("Física I", 1), ("Lengua Extranjera", 2), ("Física II", 2)])

    def test_tabla_por_la_columna_de_su_encabezado(self):
        html = """<table><tr><td>Código</td><td>Unidad curricular</td><td>Modalidad</td></tr>
        <tr><td colspan="3">Primer año</td></tr><tr><td>01</td><td>Sociología Política*</td><td>Cuatrimestral</td></tr>
        <tr><td colspan="3">Segundo año</td></tr><tr><td>09</td><td>Teoría Política II</td><td>Cuatrimestral</td></tr></table>"""
        self.assertEqual(p.plan_tabla_por_columna(html), [("Sociología Política", 1), ("Teoría Política II", 2)])

    def test_sin_la_numeracion_romana(self):
        html = """<p><strong>Primer año</strong></p><ul><li>VI.- Derecho del Trabajo I</li><li>XI. Inglés I</li></ul>"""
        self.assertEqual(p.plan_titulo_y_lista(html), [("Derecho del Trabajo I", 1), ("Inglés I", 1)])

    def test_unr_veterinaria_por_codigo(self):
        html = """<table><tr><td>Código</td><td>Asignatura</td></tr>
        <tr><td>1.1.1</td><td>Física Biológica</td><td>100</td></tr>
        <tr><td>2.8.1</td><td>Anatomía Descriptiva y Comparada II</td><td>1.5.2</td></tr></table>"""
        self.assertEqual(p.plan_por_codigo(html), [("Física Biológica", 1), ("Anatomía Descriptiva y Comparada II", 2)])

    def test_ucasal_plan_por_carrera_de_alumnos(self):
        texto = """PLAN DE ESTUDIO POR CARRERA
    1 PRIMER AÑO
      05 0000     FILOSOFÍA                                                             3      1 Sem
      50 6260     PLANIFICACIÓN, PRODUCCIÓN Y LOGÍSTICA DE EVENTOS                      6      2 Sem
    2 SEGUNDO AÑO
      00 0050     TEOLOGÍA                                                              3      1 Sem"""
        self.assertEqual(p.plan_ucasal(texto), [("Filosofía", 1), ("Planificación, Producción y Logística de Eventos", 1),
                                                ("Teología", 2)])


if __name__ == "__main__":
    unittest.main()


class PlanFbqfUnt(unittest.TestCase):
    def test_takes_the_year_from_the_tab_title_not_its_id(self):
        def panel(tab, nombres):
            filas = "".join(f"<tr><td>{n}</td><td>Cuatrimestral</td><td>–</td></tr>" for n in nombres)
            return (f'<div data-tab-id="{tab}"><table><tr><td>Asignatura</td><td>Regimen</td>'
                    f"<td>Correlativas</td></tr>{filas}</table></div>")
        html = ('<div id="plan"><ul><li data-title-tab-id="1"><h6>1<sup>er</sup> año</h6></li>'
                '<li data-title-tab-id="2"><h6>2<sup>do</sup> año</h6></li>'
                '<li data-title-tab-id="6"><h6>3<sup>er</sup> año</h6></li></ul>'
                + panel(1, ["Matemática I", "Física I"]) + panel(2, ["Biología"])
                + panel(6, ["Trabajo Final", "Demostrar conocimiento de Inglés Técnico"]) + "</div>")
        self.assertEqual(p.plan_fbqf_unt(html),
                         [("Matemática I", 1), ("Física I", 1), ("Biología", 2), ("Trabajo Final", 3)])


class PlanFahceCatedras(unittest.TestCase):
    def test_takes_the_capitals_and_the_slots_not_the_options(self):
        def catedra(n, texto):
            return f'<li><a href="/deptos/historia/catedras/catedra-{n}">{texto}</a></li>'
        nombres = [f"HISTORIA GENERAL {r}" for r in ("I", "II", "III", "IV", "V", "VI")] + [
            "HISTORIA ARGENTINA I", "HISTORIA ARGENTINA II", "HISTORIA AMERICANA I", "HISTORIA AMERICANA II",
            "SOCIOLOGÍA GENERAL", "INTRODUCCIÓN A LA HISTORIA", "TEORÍA SOCIAL CONTEMPORÁNEA A", "FILOSOFÍA"]
        html = "<ul>" + "".join(catedra(i, n) for i, n in enumerate(nombres)) + catedra(90, "DE LAS CIENCIAS") \
            + catedra(91, "Cinco OPTATIVAS LIBRES a elegir entre") + catedra(92, "Historia de Asia y África") \
            + "".join(catedra(93 + i, f"Materia optativa {r}") for i, r in enumerate(("I", "II", "III", "IV", "V"))) \
            + catedra(99, "Seminario de licenciatura I") + catedra(100, "Francés") + "</ul>"
        materias = [nombre for nombre, anio in p.plan_fahce_unlp(html)]
        self.assertIn("Teoría Social Contemporánea A", materias)
        self.assertIn("Filosofía de las Ciencias", materias)
        self.assertIn("Materia optativa V", materias)
        self.assertNotIn("Historia de Asia y África", materias)
        self.assertNotIn("Francés", materias)
        self.assertEqual(len(materias), 20)
