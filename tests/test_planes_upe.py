import unittest

from rumbo_scraper.parsers.planes_sitios import plan_upe_de


def _palabra(x, y, texto, x2=None, y2=None):
    return f'<word xMin="{x}" yMin="{y}" xMax="{x2 or x + 6 * len(texto)}" yMax="{y2 or y + 10}">{texto}</word>'


class PlanUpe(unittest.TestCase):
    def test_nombres_partidos_y_cuatrimestres_entre_reglas(self):
        palabras = [
            _palabra(157, 204, "Asignatura"), _palabra(253, 204, "Horaria"),
            # The terms' labels turned on their side: "Cuatrimestre" above its "1°".
            _palabra(97, 240, "Cuatrimestre", 109, 290), _palabra(97, 292, "1°", 109, 300),
            _palabra(97, 340, "Cuatrimestre", 109, 380), _palabra(97, 382, "2°", 109, 390),
            _palabra(97, 405, "Cuatrimestre", 109, 445), _palabra(97, 447, "3°", 109, 455),
            _palabra(126, 249, "1"), _palabra(142, 239, "Introducción"), _palabra(142, 249, "al"),
            _palabra(160, 249, "Campo"), _palabra(142, 259, "Profesional"), _palabra(265, 249, "32"),
            _palabra(126, 290, "2"), _palabra(142, 290, "Gestión"), _palabra(190, 290, "Logística"),
            _palabra(240, 290, "l"), _palabra(265, 290, "64"),
            _palabra(126, 345, "3"), _palabra(142, 340, "Fundamentos"), _palabra(142, 350, "de"),
            _palabra(160, 350, "Economía"), _palabra(265, 345, "64"),
            _palabra(123, 400, "4"), _palabra(142, 400, "Matemática"), _palabra(265, 400, "64"),
        ]
        cajas = "<page>" + "".join(palabras) + "</page>"
        # The rules: the second term's cell holds row 3 alone, though its label
        # reaches nearer row 4; the rows' own rules stop short of the labels' column.
        reglas = {0: [(235, 38, 559), (330, 93, 559), (310, 117, 559), (395, 93, 559), (470, 38, 559)]}
        self.assertEqual(plan_upe_de(cajas, reglas), [
            ("Introducción al Campo Profesional", 1), ("Gestión Logística I", 1),
            ("Fundamentos de Economía", 1), ("Matemática", 2)])

    def test_sin_las_reglas_de_un_rotulo_no_lee(self):
        cajas = ("<page>" + _palabra(157, 204, "Asignatura") + _palabra(253, 204, "Horaria")
                 + _palabra(97, 240, "1°") + _palabra(110, 240, "Cuatrimestre")
                 + _palabra(126, 249, "1") + _palabra(142, 249, "Matemática") + "</page>")
        self.assertEqual(plan_upe_de(cajas, {0: []}), [])



class PlanUmendozaPagina(unittest.TestCase):
    def test_pestania_del_plan(self):
        from rumbo_scraper.parsers.planes_sitios import plan_umendoza_pagina

        html = """<div class="fl-tabs-panel-content"><p>Presentación de la carrera</p></div>
<div class="fl-tabs-panel-content"><h2>Plan de estudios</h2><p><em>(s) = semestral.</em></p>
<h3>1er Año</h3><p>Derecho Romano (s)<br/>Introducción al Derecho (s) (p)</p>
<h3><strong>2do Año</strong></h3><p><strong>Ciclo de Instrumentación</strong><br/>Derecho Civil – Parte General (a)</p>
<h3>CONDICIÓN FINAL DE EGRESO</h3><p>Trabajo Final de Investigación (a)</p></div>"""
        self.assertEqual(plan_umendoza_pagina(html), [
            ("Derecho Romano", 1), ("Introducción al Derecho", 1), ("Derecho Civil – Parte General", 2)])


class PlanFhuUnse(unittest.TestCase):
    def test_modulos_y_numeros_fuera(self):
        from rumbo_scraper.parsers.planes_sitios import plan_fhu_unse

        html = """<div><p>1º AÑO</p><p>1º MODULO</p><p>12 - Anatomía General</p><p>Contabilidad I</p>
<p>Salud Colectiva</p><p>Fisiología Humana</p>
<p>2º AÑO</p><p>3º MODULO</p><p>13 -Neonatología 1</p><p>Farmacología General</p><p>Psicología Social</p>
<p>Inglés Técnico</p><p>Epidemiología</p><p>Bioética</p><p>Estadística</p></div>"""
        self.assertEqual(plan_fhu_unse(html), [
            ("Anatomía General", 1), ("Contabilidad I", 1), ("Salud Colectiva", 1), ("Fisiología Humana", 1),
            ("Neonatología 1", 2), ("Farmacología General", 2), ("Psicología Social", 2), ("Inglés Técnico", 2),
            ("Epidemiología", 2), ("Bioética", 2), ("Estadística", 2)])

    def test_nombres_pegados_no_se_leen(self):
        from rumbo_scraper.parsers.planes_sitios import plan_fhu_unse

        html = "<div><p>Primer Año</p><p>Macroeconomía</p><p>Finanzas PúblicasIngl</p><p>Segundo Año</p><p>Impuestos I</p></div>"
        self.assertEqual(plan_fhu_unse(html), [])


class PlanAgroUba(unittest.TestCase):
    TEXTO = """                    PLAN DE ESTUDIOS DE LA LICENCIATURA
                                   Primer Año (CBC)
            Primer cuatrimestre                                    Segundo cuatrimestre
Matemática (9)                                          Biología (6)
   Cod 5. Química (6) CBC
                            Ciclo Profesional – Segundo Año
Química Aplicada (6)                                    Bioquímica Aplicada (4)
*CBC                                                    *Biomoléculas (regular para cursar)
Requisitos exigidos a los estudiantes para obtener el título:
Cumplir con Asignaturas Optativas (10)
"""

    def test_dos_columnas_por_anio(self):
        from rumbo_scraper.parsers.planes_sitios import plan_agro_uba

        self.assertEqual(plan_agro_uba(self.TEXTO), [
            ("Matemática", 1), ("Biología", 1), ("Química", 1), ("Química Aplicada", 2), ("Bioquímica Aplicada", 2)])

    def test_nombre_partido_no_se_lee(self):
        from rumbo_scraper.parsers.planes_sitios import plan_agro_uba

        texto = self.TEXTO.replace("Química Aplicada (6)", "Taller de Práctica II: Interacción con la realidad\n(2)")
        self.assertEqual(plan_agro_uba(texto), [])


class PlanAgrariasUnca(unittest.TestCase):
    def test_la_ventana_de_la_carrera(self):
        from rumbo_scraper.parsers.planes_sitios import plan_agrarias_unca

        html = """<div><h3>Ingeniería de Paisajes</h3><p>Mas Información</p><h4>Ingeniería de Paisajes</h4><p>×</p>
<p>Grilla de Materias</p><p>Primer Año</p><ul><li>Biología (1c)</li><li>Física (2c)</li></ul>
<p>Segundo Año</p><ul><li>Suelo (anual)</li></ul><a>Plan de Estudio 2025</a>
<h4>Ingeniería Agronómica​</h4><p>×</p><p>Primer Año</p><ul><li>Botánica Morfológica (1c)</li></ul></div>"""
        self.assertEqual(plan_agrarias_unca(html, "Ingeniería de Paisajes"),
                         [("Biología", 1), ("Física", 1), ("Suelo", 2)])
        self.assertEqual(plan_agrarias_unca(html, "Ingeniería Agronómica"), [("Botánica Morfológica", 1)])
        self.assertEqual(plan_agrarias_unca(html, "Ingeniería en Alimentos"), [])


class PlanFiloUnt(unittest.TestCase):
    HTML = """<div><div>1° y 2° año · iguales en los dos títulos</div>
<div><div><div><div>1°</div><div>AÑO</div></div><div>Lógica</div><div>Ética</div></div></div>
<details><summary><div><div>Profesorado en Filosofía</div><div>Carga horaria total: 3000 h</div></div><div>+</div></summary>
<p><span><span><span><span>2°</span><span>Año</span></span><span>Didáctica</span></span></span></p></details>
<details><summary><div><div>Licenciatura en Filosofía (Plan 2018)</div><div>3 materias</div></div></summary>
<div><div><div><div>2°</div><div>AÑO</div></div><div><div>Metafísica</div></div></div></div></details>
<details><summary><div><div>Licenciatura en Francés · Orientación Literatura</div></div></summary></details></div>"""

    def test_el_plan_de_cada_titulo(self):
        from rumbo_scraper.parsers.planes_sitios import plan_filo_unt_pagina as plan_filo_unt

        self.assertEqual(plan_filo_unt(self.HTML, "Profesorado de Filosofía"),
                         [("Lógica", 1), ("Ética", 1), ("Didáctica", 2)])
        # Its heading says 3 subjects, its column has 1.
        self.assertEqual(plan_filo_unt(self.HTML, "Licenciatura en Filosofía"), [])
        self.assertEqual(plan_filo_unt(self.HTML, "Licenciatura en Francés"), [])


class PlanUdc(unittest.TestCase):
    def test_la_parte_de_cada_carrera(self):
        from rumbo_scraper.parsers.planes_sitios import plan_udc

        def anio(titulo, contenido):
            return (f'<div class="elementor-toggle-item"><div class="elementor-tab-title"><a>{titulo}</a></div>'
                    f'<div class="elementor-tab-content">{contenido}</div></div>')
        html = (anio("PNU", "<ul><li>Matemáticas</li></ul>")
                + anio("1er Año", "<ul><li>Programación 1</li><li>Trabajo final (<strong>sólo para la Tecnicatura</strong>)</li>"
                       "<li>Taller de Inglés I – 1er. cuatrimestre</li></ul>")
                + anio("2do Año", "<p>*Las siguientes materias son exclusivas de la Licenciatura*</p><ul><li>Tesis</li></ul>"))
        self.assertEqual(plan_udc(html, "Tecnicatura Universitaria en Redes"),
                         [("Programación 1", 1), ("Trabajo final", 1), ("Taller de Inglés I", 1)])
        self.assertEqual(plan_udc(html, "Licenciatura en Redes"),
                         [("Programación 1", 1), ("Taller de Inglés I", 1), ("Tesis", 2)])

    def test_otras_marcas(self):
        from rumbo_scraper.parsers.planes_sitios import plan_udc

        html = ('<div class="elementor-toggle-item"><div class="elementor-tab-title"><a>1er Año</a></div>'
                '<div class="elementor-tab-content"><p>Primer cuatrimestre</p><ul><li>Ecología</li>'
                '<li>Taller de Mecánica (solo Tecnicatura)</li></ul><p>Segundo cuatrimestre Tecnicatura Universitaria</p>'
                '<ul><li>Trabajo Final</li></ul><p>Segundo cuatrimestre Licenciatura</p><ul><li>Microeconomía</li></ul></div></div>'
                '<div class="elementor-toggle-item"><div class="elementor-tab-title"><a>2do Año</a></div>'
                '<div class="elementor-tab-content"><p>*solo Licenciatura*</p><p>Tesina – anual.</p></div></div>')
        self.assertEqual(plan_udc(html, "Tecnicatura Universitaria en Guardaparque"),
                         [("Ecología", 1), ("Taller de Mecánica", 1), ("Trabajo Final", 1)])
        self.assertEqual(plan_udc(html, "Licenciatura en Áreas Naturales"),
                         [("Ecología", 1), ("Microeconomía", 1), ("Tesina", 2)])


class PlanUnrn(unittest.TestCase):
    def test_ficha_con_nombres_partidos(self):
        from rumbo_scraper.parsers.planes_sitios import plan_unrn

        texto = """                                           PLAN DE ESTUDIOS
Código    Nº de   Asignatura                        Hs.
                                     PRIMER AÑO
                               PRIMER CUATRIMESTRE
T0001     1       Razonamiento y Resolución de Problemas                  4         64          -
T0002     2       Introducción a la Lectura y Escritura
                                                                          4         64          -
                  Académica
                                    SEGUNDO AÑO
                  Solución de controversias y Derecho internacional
VR328     3                                                              4         64          12
                  aplicado
                                             Subtotal Segundo Año:       48          640
TITULO: LICENCIADO EN COMERCIO EXTERIOR
"""
        self.assertEqual(plan_unrn(texto), [
            ("Razonamiento y Resolución de Problemas", 1), ("Introducción a la Lectura y Escritura Académica", 1),
            ("Solución de controversias y Derecho internacional aplicado", 2)])
        self.assertEqual(plan_unrn(texto.replace("VR328     3", "VR328     4")), [])


if __name__ == "__main__":
    unittest.main()


class PlanUnmaTests(unittest.TestCase):
    def test_codigo_y_nombre_en_su_caja(self) -> None:
        from rumbo_scraper.parsers.planes_sitios import _CODIGO_UNMA
        texto = ("(cód. 17) Movimientos\nSociales en América\nLatina (C)\nCorr.: 01 y 02\n"
                 "(cód. 18) Seminario\nTemático Obligatorio III\n(B)\n(cód. 32) Seminario de\nActualización Teórica\n"
                 "(cód. 33) Seminario de\nActualización Teórica (C)\n")
        hallados = {int(c): " ".join(n.split()) for c, n in _CODIGO_UNMA.findall(texto)}
        self.assertEqual(hallados, {17: "Movimientos Sociales en América Latina",
                                    18: "Seminario Temático Obligatorio III",
                                    33: "Seminario de Actualización Teórica"})


class PlanFavaloroTests(unittest.TestCase):
    def test_un_panel_por_anio(self) -> None:
        from rumbo_scraper.parsers.planes_sitios import plan_favaloro
        html = ('<div class="vc_tta-panel" id="primero"><ul><li><h2>Curso de Ingreso</h2></li>'
                '<li><h2>Anatomía</h2><p>Carga Horaria</p></li><li><h2>Bioquímica</h2></li></ul></div>'
                '<div class="vc_tta-panel" id="segundo"><ul><li><h2>Fisiología</h2></li></ul></div>'
                '<div class="vc_tta-panel" id="quinto"></div>')
        self.assertEqual(plan_favaloro(html), [("Anatomía", 1), ("Bioquímica", 1), ("Fisiología", 2)])


class PlanTotalesPorAnioTests(unittest.TestCase):
    def test_cada_fila_va_al_anio_cuyos_totales_siguen(self) -> None:
        from rumbo_scraper.parsers.planes_sitios import plan_totales_por_anio
        texto = """
    Año        Cuatrimestre                 Actividades curriculares               Carga horaria total
                                Infancias                                                  500
                     1°
     1°                         Orígenes de la Psicología                                  250
              Totales primer año                                                          1500
              1º          Electrotecnia                                               48           48           96
            Anual
                           Introducción a la práctica en I+D                           64           128          192
              Totales de segundo año                                                     1500
"""
        self.assertEqual(plan_totales_por_anio(texto), [
            ("Infancias", 1), ("Orígenes de la Psicología", 1), ("Electrotecnia", 2),
            ("Introducción a la práctica en I+D", 2)])

    def test_sin_el_primer_anio_no_hay_plan(self) -> None:
        from rumbo_scraper.parsers.planes_sitios import plan_totales_por_anio
        self.assertEqual(plan_totales_por_anio("  Electrotecnia     96\n  Totales de segundo año   960\n"), [])


class PlanIuseTests(unittest.TestCase):
    def test_filas_numeradas_bajo_cada_anio(self) -> None:
        from rumbo_scraper.parsers.planes_sitios import plan_iuse
        texto = """
                           Primer año                                                             1° Cuatrimestre
   1      Sociología y conocimiento científico                                 4             64          Cuatrimestral
   2      Criminalística                                                       4             64          Cuatrimestral
                                                                               21            336
                         Segundo año                                                              1° Cuatrimestre
   3      Inglés II                                                            3             48          Cuatrimestral
"""
        self.assertEqual(plan_iuse(texto), [("Sociología y conocimiento científico", 1), ("Criminalística", 1),
                                            ("Inglés II", 2)])
        self.assertEqual(plan_iuse(texto.replace("   2      Criminalística", "   9      Criminalística")), [])


class PlanFolletoColumnasTests(unittest.TestCase):
    def test_cortes_y_continuaciones(self) -> None:
        from rumbo_scraper.parsers.planes_sitios import _CONTINUA, _CORTADO_EN, _ETIQUETA_DE_FOLLETO, _FIN_DE_FOLLETO
        self.assertTrue(_CONTINUA.match("del Adulto"))
        self.assertFalse(_CONTINUA.match("Derecho Penal I"))
        self.assertTrue(_CORTADO_EN.search("Fundamentos de Enfermería y"))
        self.assertTrue(_ETIQUETA_DE_FOLLETO.match("PRIMER QUARTER"))
        self.assertTrue(_ETIQUETA_DE_FOLLETO.match("- Nutrición Clínica"))
        self.assertTrue(_FIN_DE_FOLLETO.match("Otras Actividades"))
        self.assertFalse(_FIN_DE_FOLLETO.match("Teoría del Derecho"))


class PlanUntrefTests(unittest.TestCase):
    def test_por_anio_o_por_cuatrimestre(self) -> None:
        from rumbo_scraper.parsers.planes_sitios import plan_untref
        html = ('<div class="carreras-grid"><div class="carreras-tit"><p><strong>Plan de estudios</strong></p></div>'
                '<div class="col"><div class="block"><div class="content-block">'
                '<p>PRIMER CUATRIMESTRE</p><ul><li>Gramática I</li><li>Literatura medieval (optativa)</li></ul>'
                '<p>TERCER CUATRIMESTRE</p><ul><li>Gramática II</li><li>Trayectos Formativos Alternativos</li></ul>'
                '<p><strong>Temáticas ofrecidas</strong></p><p>- Etnografía</p></div></div></div></div>')
        self.assertEqual(plan_untref(html), [("Gramática I", 1), ("Gramática II", 2)])
