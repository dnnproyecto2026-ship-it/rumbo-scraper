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
        # (The detailed-prerequisites sheets name each unit whole, wrapped over lines; a name cut short is dropped.)
        self.assertEqual(p.plan_ucasal("CORRELATIVIDADES DETALLADAS\n 1 ° Año\n05 0000    FILOSOFIA   3   1 Sem."), [("Filosofía", 1)])
        self.assertEqual(p.plan_ucasal("CORRELATIVIDADES DETALLADAS\n 1 ° Año\n05 0000    PSICOLOGÍA EDUC.   3   1 Sem."), [])
        # Twenty letters at most: cut; one longer name and twenty is a whole name.
        self.assertEqual(p.plan_ucasal("  AÑO\n1° SEM.   ESTADÍSTICA APLICADA\n          FILOSOFÍA"), [])
        self.assertEqual(p.plan_ucasal("  AÑO\n1° SEM.   ESTADÍSTICA APLICADA\n          PRINCIPIOS DE ECONOMÍA POLÍTICA"),
                         [("Estadística Aplicada", 1), ("Principios de Economía Política", 1)])
        self.assertEqual(p.plan_ucasal("  AÑO\n1° SEM.   PATOLOGÌA QUIRÙRGICA\n          FILOSOFÍA"), [])
        self.assertEqual(p.plan_ucasal("  AÑO\n1° SEM.   FILOSOFÍA\n          PAISAJE I                         ELECTIVA"), [])

    def test_ucasal_folleto_une_los_nombres_partidos(self):
        texto = """  AÑO
1° CUAT.   ADMINISTRACIÓN FINANCIERA I
           ÉTICA
2° CUAT.   ADMINISTRACIÓN
           FINANCIERA II
           PRÁCTICA DE INTEGRACIÓN: PLANES DE EFICIENCIA ENERGÉTICA PARA
           DISTINTOS TIPOS DE ESTABLECIMIENTOS
CUATRIM.   SEGUROS PATRIMONIALES I (SEGUROS DE COSAS)
           PRÁCTICA PROFESIONAL (1)"""
        self.assertEqual(p.plan_ucasal(texto), [
            ("Administración Financiera I", 1), ("Ética", 1), ("Administración Financiera II", 1),
            ("Práctica de Integración: Planes de Eficiencia Energética para Distintos Tipos de Establecimientos", 1),
            ("Seguros Patrimoniales I (Seguros de Cosas)", 1), ("Práctica Profesional", 1)])

    def test_ucasal_anexo_nombre_centrado_en_su_codigo(self):
        texto = """COD        ASIGNATURA         REGIMEN     HORARIA HORARIA CORRELATIVAS              OBS.
                                                                        DICTADO
PRIMER AÑO
         FUNDAMENTOS DEL
 1                             Anual         3      90          -      Presencial
          TRABAJO SOCIAL
              PRÁCTICA
       PROFESIONALIZANTE I:
 2                             Anual         2      60          -      Presencial   1*
        INTRODUCCIÓN A LA
           INTERVENCIÓN
 3           SOCIOLOGÍA        Anual         3      90          -      Presencial

SEGUNDO AÑO
          PSICOLOGÍA DEL
 4     DESARROLLO Y DE LA      Anual         3      90          -      Presencial
            SUBJETIVIDAD
                                                     IF-2022-01530633-APN-DNGU#ME
COD        ASIGNATURA          REGIMEN     HORARIA HORARIA CORRELATIVAS              OBS.
                                                          35-36- 37-38-39-
        TALLER DE TRABAJO
 5                              Anual         3      90      40- 41- 42-     Presencial   9*
      INTEGRADOR FINAL (TIF)
                                                           43-44-45-46-47

TÍTULO: LICENCIADO/A EN TRABAJO SOCIAL"""
        self.assertEqual(p.plan_ucasal(texto), [
            ("Fundamentos del Trabajo Social", 1), ("Práctica Profesionalizante I: Introducción a la Intervención", 1),
            ("Sociología", 1), ("Psicología del Desarrollo y de la Subjetividad", 2),
            ("Taller de Trabajo Integrador Final (TIF)", 2)])
        # A name whose lines do not centre on its code: unread.
        self.assertEqual(p.plan_ucasal(texto.replace("           INTERVENCIÓN\n", "")), [])

    def test_ucasal_nomina_de_asignaturas(self):
        texto = """             CONTENIDOS MINIMOS POR AREA
                 ●     Fundamentos de Química
Nómina de Asignaturas por régimen de cursado, carga horaria y sistema de correlatividades
Código    Asignatura                                               a
                                        PRIMER AÑO
          Filosofía                                    1º Sem.     2        32              -            -
1.1
          Fundamentos de Química                       1º Sem.     5        80                           -
1.2
                                                                                        1.1             1.1
1.3       Anatomía y Fisiología                        2º Sem.     5        80
                                                                                        1.2             1.2
                      TOTAL                                                            784 hrs.
                                       SEGUNDO AÑO
                                                                                        1.3
2.1      Nutrición y Alimentación Animal               1º Sem      5        80                          1.3
Universidad Católica de Salta
2.2                                                2º Sem.   2   32           2.1            2.1
        Ética Profesional I
TOTAL                                                                  768 hrs."""
        self.assertEqual(p.plan_ucasal(texto), [
            ("Filosofía", 1), ("Fundamentos de Química", 1), ("Anatomía y Fisiología", 1),
            ("Nutrición y Alimentación Animal", 2), ("Ética Profesional I", 2)])
        # A year with a code more than its names: unread.
        self.assertEqual(p.plan_ucasal(texto.replace("2.2     ", "2.3     ")), [])


        self.assertEqual(p.plan_ucasal("CORRELATIVIDADES DETALLADAS\n 1 ° Año\n05 0000    FILOSOFIA   3   1 Sem."), [("Filosofía", 1)])
        self.assertEqual(p.plan_ucasal("CORRELATIVIDADES DETALLADAS\n 1 ° Año\n05 0000    PSICOLOGÍA EDUC.   3   1 Sem."), [])

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

    def test_ucasal_tabla_con_codigo(self):
        texto = """PLAN DE ESTUDIOS                                                FACULTAD DE
LICENCIATURA EN CRIMINOLOGÍA                                    CIENCIAS JURÍDICAS
                                           PRIMER AÑO
                            1er Semestre
 Cód.                                                      Régimen    por semestre de
                             MATERIA
  1     Filosofía I                                      Semestral  3         -   48
        Negociación comercial, transcultural y
  6                                                        Semestral     4         64
        relaciones humanas
                                                         TOTAL DE HORAS DEL SEMESTRE
               Facultad de Ciencias Jurídicas | sead.juridicas@ucasal.edu.ar
PLAN DE ESTUDIOS                                                FACULTAD DE
LICENCIATURA EN CRIMINOLOGÍA                                    CIENCIAS JURÍDICAS
                                           SEGUNDO AÑO
  11    Teología I                                    Semestral      3       -             48
        Seminario: Técnicas de Comunicación Científica
                                               -      Semestral      4       -             64
  14
        Criminológica
     Seminario: Investigación Criminal en Lavado de Semestral    4       -              64
  32
     activos
        Teología II                                   Semestral    2       -             32
  14
  15    Seguridad Pública                             Semestral      4       -             64
                                 SEMINARIOS ELECTIVOS
  Técnicas de resolución de conflictos."""
        self.assertEqual(p.plan_ucasal(texto), [
            ("Filosofía I", 1), ("Negociación comercial, transcultural y relaciones humanas", 1),
            ("Teología I", 2), ("Seminario: Técnicas de Comunicación Científica Criminológica", 2),
            ("Seminario: Investigación Criminal en Lavado de activos", 2), ("Teología II", 2),
            ("Seguridad Pública", 2)])
        # A code whose name is drawn, not written: the plan is not read.
        self.assertEqual(p.plan_ucasal(texto.replace("  1     Filosofía I    ", "  1                ")), [])

    def test_unq_los_cursos_obligatorios_de_cada_nucleo(self):
        html = """<p>Ciclo Introductorio</p><table>
        <tr><td>Cursos</td><td>Horas semanales</td><td>Créditos</td></tr>
        <tr><td>Lectura y escritura académica</td><td>5</td><td>10</td></tr>
        <tr><td>Matemática</td><td>5</td><td>10</td></tr>
        <tr><td>Total Ciclo Introductorio</td><td></td><td>20</td></tr></table>
        <p>Cursos del Ciclo Superior</p><table>
        <tr><td>Cursos</td><td>Horas semanales</td><td>Créditos</td></tr>
        <tr><td>Núcleo Obligatorio</td><td></td><td></td></tr>
        <tr><td>Pedagogía</td><td>5</td><td>10</td></tr>
        <tr><td>Curso Electivo 1</td><td>5</td><td>10</td></tr>
        <tr><td>Núcleo Electivo</td><td></td><td></td></tr>
        <tr><td>Mención: Gestión</td><td></td><td></td></tr>
        <tr><td>Economía de la educación</td><td>4</td><td>8</td></tr>
        <tr><td>Otros requisitos</td><td></td><td></td></tr>
        <tr><td>Inglés</td><td>3</td><td>10</td></tr></table>
        <p>Núcleo de cursos electivos</p><table>
        <tr><td>Cursos</td><td>Horas semanales</td><td>Créditos</td></tr>
        <tr><td>Historia de los medios</td><td>5</td><td>10</td></tr></table>"""
        self.assertEqual(p.plan_unq_cursos(html), [("Lectura y escritura académica", None), ("Matemática", None),
                                                   ("Pedagogía", None), ("Inglés", None)])
        # A table whose credits do not add up to its total is a pool to choose from.
        self.assertEqual(p.plan_unq_cursos(html.replace("<td>20</td>", "<td>40</td>")), [])
        # A page with an orientation, or a table going on without its heading row, is not read.
        self.assertEqual(p.plan_unq_cursos(html.replace("Cursos del Ciclo Superior",
                                                        "Núcleo de Orientación en Periodismo")), [])
        self.assertEqual(p.plan_unq_cursos(html + """<table><tr><td>Sexto cuatrimestre</td></tr>
        <tr><td>Lógica</td><td>6</td><td>12</td></tr></table>"""), [])


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


class PlanUcongreso(unittest.TestCase):
    def _materia(self, nombre):
        return (f'<p class="materia"><span>+</span> {nombre} </p>'
                '<span style="display:none;"><a class="materia"> Mendoza</a><a class="materia"> San Juan</a></span>')

    def test_a_tab_per_year(self):
        def pestana(n, nombres):
            return f'<div class="tab-content" data-tabs-number="{n}"><div class="materias">' \
                + "".join(self._materia(x) for x in nombres) + "</div></div>"
        html = ('<div class="tabs careers-tabs"><div class="tab-labels">'
                '<a class="tab-label" data-tabs-number="1">1º AÑO</a><a class="tab-label" data-tabs-number="2">2º AÑO</a>'
                '</div><div class="tab-contents">' + pestana(1, ["Administración I (*)", "1º SEMESTRE", "Economía I"])
                + pestana(2, ["(*) Régimen promocional: 12 espacios curriculares", "Costos"]) + "</div></div>")
        self.assertEqual(p.plan_ucongreso(html), [("Administración I", 1), ("Economía I", 1), ("Costos", 2)])

    def test_tabs_of_plans_take_the_first(self):
        def plan(n, lineas):
            return f'<div class="tab-content" data-tabs-number="{n}"><div class="materias">' \
                + "".join(self._materia(x) for x in lineas) + "</div></div>"
        html = ('<div class="tabs careers-tabs"><div class="tab-labels">'
                '<a class="tab-label" data-tabs-number="1">Plan</a><a class="tab-label" data-tabs-number="2">Plan 2018</a>'
                '</div><div class="tab-contents">' + plan(1, ["Primer Año", "Derecho Político", "Segundo Año", "Obligaciones"])
                + plan(2, ["Primer Año", "Derecho Romano"]) + "</div></div>")
        self.assertEqual(p.plan_ucongreso(html), [("Derecho Político", 1), ("Obligaciones", 2)])


class PlanIupa(unittest.TestCase):
    TEXTO = """
      PRIMER AÑO
 01   Educación Musical I                        2     64              X
 02   Posicionamiento y Comercialización de      3     48         X
      Productos Audiovisuales
      Taller integrado de procedimientos y
 03   técnicas del lenguaje visual I             9    288              X
 04   Seminario Culturas Infantiles y Juveniles  2     32    X
41    Taller     Educación    mediada       por
      Tecnologías                                2     32         X
      Taller de Práctica de Conjunto I: Opción
  5                                              3     96              X
      Jazz o Rock o Tango o Folklore *
01-1  Materia de Orientación I: Canto I (sólo    2     64              X
 o    orientación en Canto)
      Total de horas primer año                 25,3   816

      SEGUNDO AÑO
 06   Instrumento Aplicado B II          (a)     2     64              X     01
 07   Horas de Asignación Libre                       230
"""

    def test_nombres_partidos_y_orientaciones(self):
        self.assertEqual(p.plan_iupa(self.TEXTO), [
            ("Educación Musical I", 1),
            ("Posicionamiento y Comercialización de Productos Audiovisuales", 1),
            ("Taller integrado de procedimientos y técnicas del lenguaje visual I", 1),
            ("Seminario Culturas Infantiles y Juveniles", 1),
            ("Taller Educación mediada por Tecnologías", 1),
            ("Taller de Práctica de Conjunto I: Opción Jazz o Rock o Tango o Folklore", 1),
            ("Instrumento Aplicado B II", 2)])


class PlanEstructuraConRegimen(unittest.TestCase):
    def test_nombres_partidos_y_espacios_de_la_institucion(self):
        texto = """
   1º Año
   1    Pedagogía                                       Cuatrimestral   Materia      6 horas
        Práctica Docente I: Métodos y Técnicas de
   2                                                    Anual           Taller       5 horas
        Recolección / Instituciones Educativas
   2º Año
        Práctica Docente II: Programación de la
   3    Enseñanza/ Curriculum y Organizaciones          Anual           Taller       6 horas
        Escolares
                                                                        Seminario/
   4    Propuesta variable o complementaria 1           Cuatrimestral                3 horas
                                                                        Taller
"""
        self.assertEqual(p.plan_estructura_con_regimen(texto), [
            ("Pedagogía", 1),
            ("Práctica Docente I: Métodos y Técnicas de Recolección / Instituciones Educativas", 1),
            ("Práctica Docente II: Programación de la Enseñanza/ Curriculum y Organizaciones Escolares", 2)])


class PlanFormatoUbicacionMendoza(unittest.TestCase):
    def test_ubicacion_sobre_el_formato_y_nombre_numerado(self):
        texto = """
Denominación: 01 - Pensamiento Filosófico

Ubicación en el mapa curricular: 1° Año
Régimen de cursado: cuatrimestral, primer cuatrimestre
Formato curricular: módulo
Carga horaria semanal: 5 HC

Denominación: 08 – Práctica Profesional Docente I. Práctica docente vinculada con
escenarios y contextos

Ubicación en el mapa curricular: 1° Año
Formato curricular: práctica

Denominación: 14- Ciencias Sociales y su didáctica I

Ubicación en el diseño curricular: 2° año
Formato: módulo - taller
"""
        self.assertEqual(p.plan_formato_ubicacion(texto), [
            ("Pensamiento Filosófico", 1),
            ("Práctica Profesional Docente I. Práctica docente vinculada con escenarios y contextos", 1),
            ("Ciencias Sociales y su didáctica I", 2)])


class PlanCordoba(unittest.TestCase):
    TEXTO = """
                    PROFESORADO DE EDUCACIÓN INICIAL: 1º AÑO

                                     CAMPO DE LA FORMACIÓN GENERAL

Pedagogía                                     4         128            1                  5              Asignatura
                                                                                                           anual

                                                                                                          Seminario
Práctica Docente I:
                                              4         128            2                  6
Contextos y Prácticas Educativas

Total: 2 Unidades Curriculares

                    PROFESORADO DE EDUCACIÓN INICIAL: 2º AÑO

Desarrollo del Pensamiento Matemático         4         128            0                  4                Taller
                                                                                                           anual
                                                                                                       Asignatura 1º
                Lengua y su Didáctica         4         128            0                  4            cuatrimestre
Lengua
                                                                                                       Seminario 2º
                Alfabetización Inicial                                                                  cuatrimestre
Estudios Socioculturales y Literarios                                                                Seminario
                                            4         128             0                4
de Pueblos de Habla Inglesa I                                                                          Anual
Taller de Ciencias en la Escuela *            1         32             0                  0              Taller

Total: 5 Unidades Curriculares

                    PROFESORADO DE EDUCACIÓN PRIMARIA: 1º AÑO

Pedagogía                                     4         128            1                  5              Asignatura
Total: 1 Unidades Curriculares

Pedagogía. Práctica Docente I: Contextos y Prácticas Educativas. Lengua y su Didáctica. Alfabetización Inicial.
Desarrollo del Pensamiento Matemático. Estudios Socioculturales y Literarios de Pueblos de Habla Inglesa I.
Taller de Ciencias en la Escuela.
"""

    def test_cada_anio_contra_su_total(self):
        self.assertEqual(p.plan_cordoba("INICIAL", self.TEXTO), [
            ("Pedagogía", 1), ("Práctica Docente I: Contextos y Prácticas Educativas", 1),
            ("Desarrollo del Pensamiento Matemático", 2), ("Lengua y su Didáctica", 2),
            ("Alfabetización Inicial", 2), ("Estudios Socioculturales y Literarios de Pueblos de Habla Inglesa I", 2),
            ("Taller de Ciencias en la Escuela", 2)])

    def test_un_total_que_no_cierra_no_da_plan(self):
        self.assertEqual(p.plan_cordoba("INICIAL", self.TEXTO.replace("Total: 5", "Total: 4")), [])

    def test_un_nombre_que_el_diseno_no_escribe_no_da_plan(self):
        self.assertEqual(p.plan_cordoba("INICIAL", self.TEXTO.replace("Estudios Socioculturales y Literarios de Pueblos de Habla Inglesa I.", "")), [])


class PlanHorasIfts(unittest.TestCase):
    CON_COLUMNAS = (
        "● Cantidad de horas: 832 horas cátedra\n● Contenidos:\n"
        "Código   Espacio Curricular                 Duración   Total\n"
        + "".join(f" G{i}      Materia número {i}                  C   4 HC     64 HC\n" for i in range(1, 11))
        + "         Psicología social y coordinación de\n"
        " E1                                          C   6 HC     96 HC\n"
        "         grupos\n"
        " E2      Inglés                              C   6 HC     96 HC\n")
    SIN_COLUMNAS = "\n".join([f"G{i}\nMateria número {i}\nC" for i in range(1, 11)]
                             + ["E1", "Psicología social y coordinación de", "grupos", "C", "E2", "Inglés"])

    def test_wrapped_name_goes_where_it_is_a_cell(self):
        materias = p.plan_horas_ifts(self.CON_COLUMNAS, self.SIN_COLUMNAS)
        self.assertEqual(len(materias), 12)
        self.assertIn(("Psicología social y coordinación de grupos", None), materias)

    def test_hours_must_add_up_to_the_declared_total(self):
        self.assertEqual(p.plan_horas_ifts(
            self.CON_COLUMNAS.replace("832", "896"), self.SIN_COLUMNAS), [])


class PlanCodigosIfts(unittest.TestCase):
    FILAS = [
        "         1.1.1   Técnicas de Programación                 FTE       MO      C      9        6      96",
        "",
        "                 Administración y Gestión de Bases de",
        "                                                          FTE       MO      C      9        6      96",
        "1°/1°   1.1.2    Datos",
        "        1.2.1    Lógica Computacional                     FF        MA      C      6        4      64",
        "                Protocolo de Internet de las",
        "        1.2.2                                   FE   Mo   C   6   4   64",
        "                Cosas",
        "        2.1.1   Inglés                                   FG        MA      C      6        4      64",
    ]

    def test_el_nombre_centrado_en_su_fila(self):
        self.assertEqual(p.plan_codigos_ifts("\n".join(self.FILAS)), [
            ("Técnicas de Programación", 1), ("Administración y Gestión de Bases de Datos", 1),
            ("Lógica Computacional", 1), ("Protocolo de Internet de las Cosas", 1), ("Inglés", 2)])

    def test_un_numero_que_falta_no_da_plan(self):
        self.assertEqual(p.plan_codigos_ifts("\n".join(self.FILAS).replace("1.2.1", "1.2.3")), [])


class PlanUnahur(unittest.TestCase):
    def test_a_wrapped_name_is_the_lines_around_its_row(self):
        texto = "\n".join([
            "PRIMER AÑO       Química                     Cuatrimestral     4   64   86  150  6",
            "                 Cultura y alfabetización",
            "PRIMER AÑO                                   Cuatrimestral              68  100  4",
            "                 digital en la universidad                     2   32",
            "                 TOTAL PRIMER CUATRIMESTRE                               288  387",
            "SEGUNDO AÑO      Física II                   Cuatrimestral     4   64  111  175  7",
            "TERCER AÑO   Espacio de integración curricular II Cuatrimestral       13",
        ])
        self.assertEqual(p.plan_unahur(texto), [("Química", 1), ("Cultura y alfabetización digital en la universidad", 1),
                                                ("Física II", 2), ("Espacio de integración curricular II", 3)])

    def test_a_table_without_numbers_its_names_centred_on_their_rows(self):
        texto = "\n".join([
            "   Titulación Final: 6.000 horas - 240 créditos",
            "  UNIDAD CURRICULAR             D      CP          HIS    HIT      HTAT       HT        CRE",
            "                                         PRIMER AÑO",
            "Pedagogía                       C     CFB           4      64        61       125        5",
            "Aprendizajes y prácticas",
            "                                C     CFB           4      64        61       125        5",
            "educativas",
            "Territorio, sujetos e",
            "                                C      CIC          4      64        86       150        6",
            "instituciones",
            "                   TOTAL PRIMER AÑO                       640       760      1400        56",
            "Técnico/a universitario/a en prácticas",
            "                                                         1209      1791      3000       120",
            "socioeducativas de Biología",
            "TERCER AÑO",
            "Historia de la Nación Argentina y sus       C     CFB      3       48      77      125       5",
            "                                                13",
            "proyectos educativos",
            "Didáctica en contextos de",
            "                                    C       CFB         3       48        77       125     5",
            "Educación superior",
            "                      TOTAL CARRERA                            2379     3621       6000   240",
        ])
        # (No second year: not the whole plan.)
        self.assertEqual(p.plan_unahur_campos(texto), [])
        texto = texto.replace("TERCER AÑO", "SEGUNDO AÑO")
        self.assertEqual(p.plan_unahur_campos(texto), [
            ("Pedagogía", 1), ("Aprendizajes y prácticas educativas", 1),
            ("Territorio, sujetos e instituciones", 1),
            ("Historia de la Nación Argentina y sus proyectos educativos", 2),
            ("Didáctica en contextos de Educación superior", 2)])

    def test_the_field_before_the_length(self):
        texto = "\n".join([
            "                                                        PRIMER AÑO",
            "Matemática                                               CFB        Cuatr.    64         86         150             6",
            "Sistemas de Representación Gráﬁca                        CFB        Cuatr.    32         68         100             4",
            "                                                       SEGUNDO AÑO",
            "Gestión de la calidad                                    CFE        Cuatr.    64         86         150             6",
        ])
        self.assertEqual(p.plan_unahur_campos(texto), [("Matemática", 1), ("Sistemas de Representación Gráfica", 1),
                                                       ("Gestión de la calidad", 2)])

    def test_a_row_it_cannot_read_is_not_skipped(self):
        texto = "\n".join([
            "                                            PRIMER AÑO",
            "Pedagogía                                   C     CFB        4      64",
            "                                           SEGUNDO AÑO",
            "Tecnología educativa                      C.      CFB       2       32      68     100       4",
            "Didáctica del Chino                                          C1      CFE      3        48    77",
        ])
        self.assertEqual(p.plan_unahur_campos(texto), [("Pedagogía", 1), ("Tecnología educativa", 2),
                                                       ("Didáctica del Chino", 2)])
        # Gestión del Mantenimiento's: the length on one line, the field and hours on the next.
        partida = texto + "\n".join(["", "Economía y Costo del ciclo de vida de los",
                                     "                                                    C        CFE      4",
                                     "Activos                                                                       64       61"])
        self.assertEqual(p.plan_unahur_campos(partida), [])


class PlanUnahurNumerado(unittest.TestCase):
    # UNAHUR's Tecnicatura en Metalurgia, abridged.
    TEXTO = "\n".join([
        "Códi-                     Asignatura                      Régimen         Carga     Carga",
        "                                                    1° Cuatrimestre",
        "",
        "1       Introducción a la Metalurgia                      Cuatrimestral   4         64        -",
        "2       Introducción al Análisis Matemático               Cuatrimestral   4         64        -",
        "        Nuevos entornos y lenguajes: la producción",
        "3                                                         Cuatrimestral   2         32        -",
        "        de conocimiento en la cultura digital",
        "4       Química                                           Cuatrimestral   4         64        -",
        "",
        "                                                    3° Cuatrimestre",
        "",
        "5       Metalurgia ll                                     Cuatrimestral   6         96        8         3",
        "        Créditos                                                                    80                  20",
        "6       Ajena                                             Cuatrimestral   6         96",
    ])

    def test_the_name_around_its_row_and_two_terms_a_year(self):
        self.assertEqual(p.plan_unahur_numerado(self.TEXTO), [
            ("Introducción a la Metalurgia", 1), ("Introducción al Análisis Matemático", 1),
            ("Nuevos entornos y lenguajes: la producción de conocimiento en la cultura digital", 1),
            ("Química", 1), ("Metalurgia II", 2)])

    def test_a_line_no_row_takes_gives_nothing(self):
        # Below a named row with nothing above it, a line in upper case is no
        # part of its name.
        texto = self.TEXTO.replace("4       Química   ", "4       Química\n        General   ")
        self.assertEqual(p.plan_unahur_numerado(texto), [])
        self.assertEqual(p.plan_unahur_numerado(self.TEXTO.replace("4       Química", "7       Química")), [])

    def test_a_name_going_on_below_its_row_and_the_field_first(self):
        # Viverismo's annex: the field right after the name, a name going on
        # below its row, the page's motto and the credits the plan counts apart.
        texto = "\n".join([
            "      Código                  Asignatura              Campo        Carga       Carga horaria",
            "                                                    1° año",
            "                                                1° cuatrimestre",
            "      1            Introducción al                    CFE           4               64",
            "                   viverismo",
            "",
            "      2            Ateneo de estudio de casos         CIC           4               64",
            "                                                    “75 avo aniversario de la gratuidad universitaria”",
            "3    Nuevos entornos y                     CFC          2   32",
            "     lenguajes: la producción de",
            "     conocimiento en la cultura",
            "     digital",
            "",
            "                                      3° cuatrimestre",
            "4    Floricultura                          CIC                   1",
            "",
            "                               15 créditos incluidos en materias (60 horas)",
            "                        CARGA HORARIA TOTAL                                   1.424",
        ])
        self.assertEqual(p.plan_unahur_numerado(texto), [
            ("Introducción al viverismo", 1), ("Ateneo de estudio de casos", 1),
            ("Nuevos entornos y lenguajes: la producción de conocimiento en la cultura digital", 1),
            ("Floricultura", 2)])

    def test_years_and_a_named_row_centred_between_lines(self):
        # Enfermería's RCS 385/2024, abridged.
        texto = "\n".join([
            "                                                           Primer Ciclo",
            "                                                              1° Año",
            "       Introducción a la Salud",
            " 1                                                 C            4          64        64        86    150    6",
            "       Comunitaria",
            " 2     Créditos ACA                                C           2           32        32        68    100    4",
            "                                                              2° Año",
            "     Deontología y aspectos legales",
            " 3   del ejercicio profesional de la        C         2        32        32                68       100     4",
            "     Enfermería",
            "     Práctica pre- Profesional          Mensual",
            " 4                                                  20 (6)    100                100       125      225     9",
            "     Supervisada I                        (5)",
            "              Enfermero/a Universitario/a                    1977      1356      621      2523     4500    180",
            "                                                  Segundo Ciclo",
            "                                                     3° Año",
            "                                                                 11",
            " 5   Ética y Desarrollo Profesional         C         2        32        32                43        75     3",
            "                    TOTAL DE HORAS                            3357     2268      1089     4143     7500    300",
        ])
        self.assertEqual(p.plan_unahur_numerado(texto), [
            ("Introducción a la Salud Comunitaria", 1),
            ("Deontología y aspectos legales del ejercicio profesional de la Enfermería", 2),
            ("Práctica pre- Profesional Supervisada I", 2), ("Ética y Desarrollo Profesional", 3)])


class PlanTablasPorAnio(unittest.TestCase):
    HTML = ("<html><head><title>Contador Público – Facultad</title></head><body><article>"
            "<h3>Plan Vigente – Plan de Estudios 2019</h3>"
            "<table><tr><td>Primer Año</td><td>Segundo Año</td></tr>"
            "<tr><td>Contabilidad I</td><td>Contabilidad II</td></tr>"
            "<tr><td>1º SEMESTRE</td><td>Inglés (*)</td></tr>"
            "<tr><td></td><td>Contador Público</td></tr></table>"
            "<h3>Plan de Estudios 2001</h3>"
            "<table><tr><td>Primer Año</td></tr><tr><td>Materia Vieja</td></tr></table>"
            "</article></body></html>")

    def test_reads_the_current_plan_only(self):
        self.assertEqual(p.plan_tablas_por_anio(self.HTML),
                         [("Contabilidad I", 1), ("Contabilidad II", 2), ("Inglés", 2)])

    def test_a_page_without_year_tables_is_empty(self):
        self.assertEqual(p.plan_tablas_por_anio("<html><body><table><tr><td>Nombre</td></tr></table></body></html>"), [])


class PlanUpDyc(unittest.TestCase):
    def test_materias_con_codigo_por_anio_hasta_el_titulo_final(self):
        from rumbo_scraper.parsers.planes_sitios import plan_up_dyc

        html = ("<div>1<span>er año</span><h4>1 er cuatrimestre</h4>"
                "<p>Diseño de Interiores I</p><p>020221 | 026451</p><p>VIDRIERA</p>"
                "<p>Taller de Interiores I</p><p>022575</p>"
                "<p>Diseño de Interiores I</p><p>020221 | 026451</p>"
                "<p>4</p><p>to año</p><p>Cultura II</p><p>LIBERTAD DE ELEGIR</p>"
                "<p>Trabajo Final de Grado (</p><p>Proyecto de Graduación</p><p>) 053519</p>"
                "<p>Título Final: Diseñador/a de Interiores</p>"
                "<p>1</p><p>er año</p><p>Diseño de Negocios I</p><p>099999</p></div>")
        self.assertEqual(plan_up_dyc(html), [
            ("Diseño de Interiores I", 1), ("Taller de Interiores I", 1),
            ("Cultura II", 4), ("Trabajo Final de Grado (Proyecto de Graduación)", 4)])


class PlanUnpaz(unittest.TestCase):
    def test_a_stray_prerequisite_beside_the_rest_of_a_name(self):
        # Producción y Gestión Audiovisual: the "-" far right is no part of the name.
        texto = "\n".join([
            "                                      Código     Asignatura                                        Régimen                 Semanales",
            "             Primer año",
            "                                      10         Taller de edición                                 Cuatrimestral           4hs                 04",
            "                                      11         Taller de realización y                           Cuatrimestral           4hs                 04-10",
            "                                                 producción audiovisual I                                                                      -",
            "                                      12         Producción operativa integral                     Cuatrimestral           4hs                 04",
        ])
        self.assertEqual(p.plan_unpaz(texto), [
            ("Taller de edición", 1), ("Taller de realización y producción audiovisual I", 1),
            ("Producción operativa integral", 1)])


class PlanUnso(unittest.TestCase):
    # UNSO's plans as ``pdftotext -layout`` gives them (Abogacía, Criminalística,
    # Desarrollo de Videojuegos, Edición Audiovisual).
    def test_rows_apart_by_blank_lines(self):
        texto = "\n".join([
            "PLAN DE ESTUDIOS",
            "TECNICATURA UNIVERSITARIA EN CRIMINALÍSTICA",
            "",
            " ASIGNATURA                                  HS. TOTALES   HS. TEÓRICAS   HS. PRACTICAS",
            "",
            " PRIMER AÑO",
            "",
            " PRIMER CUATRIMESTRE",
            "",
            " Elementos de Derecho Civil, Comercial y         64             32             32",
            " Laboral",
            "",
            " Taller de búsqueda Jurídica y análisis",
            "                                                 64             16             48",
            " Jurisprudencial",
            "",
            " Legales y comerciales                                          36             12",
            "                                                 48",
            "",
            " Metodología de la Investigación                 64             32             32",
            " en Cs. Sociales",
            " SUBTOTAL                                        256            112            144",
            "  SEGUNDO CUATRIMESTRE",
            "",
            "  Química                                                      64                 32                32",
            "  TOTAL ANUAL",
            "",
            "  Psicología Criminal                                          64                 32                32",
            "",
            "  SUBTOTAL                                                    320                 144              176",
            "",
            "  TOTAL ANUAL                                                 640                 288              352",
            "",
            "  SEGUNDO AÑO",
            "",
            "  Balística Forense                                            64                 32                32",
            "",
            "  TOTAL ANUAL                                                 512                240               272",
            "",
            " Práctica Profesional Supervisada                            100                 25                75",
            "",
            " CARGA HORARIA TOTAL DE LA CARRERA                           1764                768               971",
        ])
        self.assertEqual(p.plan_unso(texto), [
            ("Elementos de Derecho Civil, Comercial y Laboral", 1),
            ("Taller de búsqueda Jurídica y análisis Jurisprudencial", 1),
            ("Legales y comerciales", 1), ("Metodología de la Investigación en Cs. Sociales", 1),
            ("Química", 1), ("Psicología Criminal", 1), ("Balística Forense", 2)])

    def test_rows_together_with_the_hours_on_the_last_line(self):
        texto = "\n".join([
            "                               Horas       Horas            Horas",
            "Asignatura                     totales     teóricas         prácticas",
            "                                Primer Año",
            "Primer cuatrimestre",
            "Producción Audiovisual 1                64            32                32",
            "Software en Edición",
            "Audiovisual                             64            16                48",
            "Postproducción Audiovisual",
            "1                                       64            32                32",
            "Subtotal                               192            80                112",
            "Total Anual                            576            272               304",
        ])
        self.assertEqual(p.plan_unso(texto), [
            ("Producción Audiovisual 1", 1), ("Software en Edición Audiovisual", 1),
            ("Postproducción Audiovisual 1", 1)])

    def test_rows_that_cannot_be_told_apart(self):
        texto = "\n".join([
            " PRIMER AÑO",
            " Química General                             64             32              32",
            " Ambiente y Territorio",
            " Biología",
            " SUBTOTAL                                    256            110             146",
        ])
        self.assertEqual(p.plan_unso(texto), [])


class PlanUnahurCeldas(unittest.TestCase):
    FILAS = [
        ["Licenciatura en Desarrollo Agrario", None, None, None],
        ["Código", "Asignatura", "Campo", "Correlatividad"],
        ["1er año", None, None, None],
        ["1er cuatrimestre", None, None, None],
        ["1", "Introducción al desarrollo\nagrario", "CFE", "-"],
        ["2", "UNAHUR I (asignatura\nelectiva)", "CFC", "-"],
        ["2° Año", None, None, None],
        ["3ercuatrimestre", None, None, None],
        ["3", "Química general", "CFB", "1"],
        ["Ateneo de casos de estudio", "5", None, None],
        ["4", "Ajena", "CFB", "-"],
    ]

    def test_each_row_its_cell_and_the_year_above(self):
        self.assertEqual(p.plan_unahur_celdas(self.FILAS), [
            ("Introducción al desarrollo agrario", 1), ("UNAHUR I (asignatura electiva)", 1),
            ("Química general", 2)])

    def test_a_number_or_a_year_out_of_order_gives_nothing(self):
        filas = [list(f) for f in self.FILAS]
        filas[8][0] = "4"
        self.assertEqual(p.plan_unahur_celdas(filas), [])
        filas = [list(f) for f in self.FILAS]
        filas[6][0] = "3° Año"
        self.assertEqual(p.plan_unahur_celdas(filas), [])

    def test_a_row_without_its_name_gives_nothing(self):
        filas = [list(f) for f in self.FILAS]
        filas[5][1] = None
        self.assertEqual(p.plan_unahur_celdas(filas), [])


class PlanCargaHoraria(unittest.TestCase):
    def test_titulo_sobre_su_carga_horaria_y_titulo_en_la_misma_linea(self):
        texto = """3.3 ESTRUCTURA CURRICULAR
PRIMER AÑO
Psicología   Salud Pública I
Total de Horas: 736 horas

PRIMER AÑO
CAMPO DE FORMACION GENERAL

PSICOLOGÍA

        Carga Horaria: 32 horas
Alcances de los contenidos:
SEGUNDO AÑO
SALUD PÚBLICA II - Carga horaria: 2 horas reloj por semana
Prácticas de la carga horaria total
SUJETOS DE LA RECREACIÓN - Carga horaria:
Recreativos - Carga horaria: 4 horas
"""
        self.assertEqual(p.plan_carga_horaria(texto), [("Psicología", 1), ("Salud pública II", 2),
                                                        ("Sujetos de la recreación", 2)])

    def test_unidades_numeradas_y_titulo_partido_en_dos_lineas(self):
        texto = """PRIMER AÑO
1. Física para Seguridad 1 - Carga horaria: 2 (dos) módulos por semana.
SEGUNDO AÑO
17. Práctica Profesionalizante 2: Intervenciones en el campo profesional - Carga
horaria: 3 (tres) módulos por semana.
TERCER AÑO
18. Comunicación, Tecnología y Sociedad. Carga horaria: 2 (dos) módulos por semana.
"""
        self.assertEqual(p.plan_carga_horaria(texto), [
            ("Física para seguridad 1", 1),
            ("Práctica profesionalizante 2: intervenciones en el campo profesional", 2),
            ("Comunicación, tecnología y sociedad", 3)])

    def test_unidad_en_mayusculas_partida_antes_o_dentro_del_titulo(self):
        texto = """PRIMER AÑO
SUJETOS DE LA RECREACIÓN - Carga horaria: 2 horas reloj por semana
SEGUNDO AÑO
EDUCACIÓN AMBIENTAL - Carga horaria: 2 horas reloj por semana.
PRÁCTICAS PROFESIONALIZANTES II: Planificación de Proyectos Recreativos - Carga
horaria: 4 horas reloj por semana.
TERCER AÑO
PRÁCTICAS PROFESIONALIZANTES III: Diseño e Implementación de Proyectos
Recreativos - Carga horaria: 4 horas reloj por semana
"""
        self.assertEqual(p.plan_carga_horaria(texto), [
            ("Sujetos de la recreación", 1),
            ("Educación ambiental", 2),
            ("Prácticas profesionalizantes II: planificación de proyectos recreativos", 2),
            ("Prácticas profesionalizantes III: diseño e implementación de proyectos recreativos", 3)])

    def test_unidad_numerada_sin_dos_puntos(self):
        texto = """Primer año
1. Derecho - Carga horaria: 2 (dos) módulos por semana
Segundo año
12. Derecho Laboral – Carga horaria 2 (dos) módulos por semana
La carga horaria total de la Tecnicatura es de 1824 horas
"""
        self.assertEqual(p.plan_carga_horaria(texto), [("Derecho", 1), ("Derecho laboral", 2)])


class PlanUcasalCorrelatividades(unittest.TestCase):
    def test_nombres_partidos_en_varias_lineas_y_correlativas_a_la_derecha(self):
        texto = """                    PLAN DE ESTUDIO Y CORRELATIVIDADES DETALLADAS
     MATERIAS                  CR.    SEMESTRE            CORRELATIVAS PARA CURSAR
 1° Año
08 0100 DIDÁCTICA GENERAL        4    0 Anual
08 0540 SUJETO DEL               4    0 Anual
        APRENDIZAJE
08 1490 PRÁCTICA I:              4    0 Anual
        CONTEXTO,
        COMUNIDAD Y
        ESCUELA
 2° Año
07 1580 PSICOLOGÍA DEL           3    0 Anual                                             Aprob      07 0590   PSICOLOGÍA EDUCAC.
        DESARROLLO INFANTIL                                                               .
08 1495 PRÁCTICA II:             4    0 Anual    Reg.      08 1490   PRACT.I CONT.COM.ESC Aprob      08 0100   DIDACT.GRAL.
        CURRICULUM
08 9999 PSICOLOGÍA EDUC.         3    0 Anual
"""
        self.assertEqual(p.plan_ucasal(texto), [
            ("Didáctica General", 1), ("Sujeto del Aprendizaje", 1),
            ("Práctica I: Contexto, Comunidad y Escuela", 1),
            ("Psicología del Desarrollo Infantil", 2), ("Práctica II: Currículum", 2)])
