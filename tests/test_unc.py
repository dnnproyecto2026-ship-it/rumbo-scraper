"""Tests for the careers read off the UNC's official guides."""

import unittest

from rumbo_scraper.parsers.unc import leer_guia, leer_guia_unrc, nombre_de_la_carrera

GUIA = """
<h3>Carreras de Grado por orden alfabético:</h3>
<div class="carreras">
<div class="carrera"><a href="https://derecho.unc.edu.ar/alumnos/abogacia/" target="_blank"><span>Abogacía </span> | Facultad de Derecho </a></div>
<div class="carrera"><a href="https://www.eco.unc.edu.ar/carreras-de-grado-estudios/contador-publico"><span>Contador/a Público/a </span> | Facultad de Ciencias Económicas </a></div>
<div class="carrera"><a href="https://tecnologia.fcm.unc.edu.ar/tec-en-laboratorio/"><span>Tecnicatura en Laboratorio Clínico e Histopatológico</span> | Escuela de Tecnología Médica</a></div>
</div>
<p><a href="/vida-estudiantil">Ingreso UNC</a></p>
"""


PREGRADO = """
<h3>Carreras de Pregrado por Unidad Académica:</h3>
<h2 class="naranja">Colegio Nacional de Monserrat</h2>
<div class="carreras">
<div class="carrera"><a href="https://carreras.monserrat.unc.edu.ar/martillero-publico/"><span>Martillero y Corredor Público</span></a></div>
</div>
<h2 class="naranja">Facultad de Filosofía y Humanidades</h2>
<div class="carreras">
<div class="carrera"><a href="https://blogs.ffyh.unc.edu.ar/ingreso/bibliotecologia/"><span>Bibliotecólogo |</span> Escuela de Bibliotecología</a></div>
</div>
"""


class GuiaDeLaUNC(unittest.TestCase):
    def test_cada_carrera_con_su_unidad_y_su_pagina(self):
        carreras = leer_guia(GUIA, "https://www.unc.edu.ar/x", "Grado")
        self.assertEqual([(c.nombre, c.unidad, c.tipo_unidad) for c in carreras], [
            ("Abogacía", "Facultad de Derecho", "Facultad"),
            ("Contador Público", "Facultad de Ciencias Económicas", "Facultad"),
            ("Tecnicatura en Laboratorio Clínico e Histopatológico",
             "Escuela de Tecnología Médica", "Escuela"),
        ])
        self.assertEqual(carreras[0].url, "https://derecho.unc.edu.ar/alumnos/abogacia/")
        self.assertEqual(carreras[0].nivel, "Grado")

    def test_el_nombre_sin_los_dos_generos(self):
        self.assertEqual(nombre_de_la_carrera("Contador/a Público/a"), "Contador Público")
        self.assertEqual(nombre_de_la_carrera("Licenciatura en Economía"), "Licenciatura en Economía")

    def test_en_pregrado_la_unidad_es_el_encabezado_si_no_viene_al_lado(self):
        carreras = leer_guia(PREGRADO, "https://www.unc.edu.ar/x", "Pregrado")
        self.assertEqual([(c.nombre, c.unidad, c.tipo_unidad) for c in carreras], [
            ("Martillero y Corredor Público", "Colegio Nacional de Monserrat", "Escuela"),
            ("Bibliotecólogo", "Escuela de Bibliotecología", "Escuela"),
        ])


class CambiosEnLaUNC(unittest.TestCase):
    def test_la_guia_decide_que_carreras_quedan(self):
        from rumbo_scraper.database.carreras_de_guias import plan_de_cambios
        from rumbo_scraper.parsers.unc import CarreraDeLaGuia

        guia = [CarreraDeLaGuia("Licenciatura Universitaria en Astronomía", "FAMAF", "Facultad", "u", "Grado"),
                CarreraDeLaGuia("Abogacía", "Facultad de Derecho", "Facultad", "u", "Grado")]
        guardadas = [{"id": "1", "nombre_carrera": "Licenciatura en Astronomía"},
                     {"id": "2", "nombre_carrera": "Ingeniería de Microondas"}]
        cambios = plan_de_cambios(guia, guardadas)
        self.assertEqual([(c.nombre, g["id"]) for c, g in cambios["iguales"]],
                         [("Licenciatura Universitaria en Astronomía", "1")])
        self.assertEqual([c.nombre for c in cambios["nuevas"]], ["Abogacía"])
        self.assertEqual([g["nombre_carrera"] for g in cambios["retiradas"]], ["Ingeniería de Microondas"])


UNRC = """
<ul class="list-unstyled">
<li class="margin-five"> <h3 class="coloreco"><strong>Cs. Econ&oacute;micas</strong></h3></li>
  <ul>
    <li><a href="https://www.eco.unrc.edu.ar/contador-publico/">CONTADOR P&Uacute;BLICO</a></li>
    <li><a href="https://www.eco.unrc.edu.ar/tecnicatura-en-gestion-empresarial/">TECNICATURA EN GESTI&Oacute;N EMPRESARIAL</a></li>
  </ul>
<li class="margin-five"><h3><strong>Cs. Humanas</strong></h3></li>
  <ul>
    <li><a href="hhttps://www.hum.unrc.edu.ar/abogacia/">ABOGAC&Iacute;A</a></li>
    <li><a href="https://www.hum.unrc.edu.ar/lic-ef/">LICENCIATURA EN EDUCACI&Oacute;N F&Iacute;SICA -CICLO-</a></li>
  </ul>
</ul>
"""


class GuiaDeRioCuarto(unittest.TestCase):
    def test_carreras_por_facultad_sin_los_ciclos(self):
        carreras = leer_guia_unrc(UNRC)
        self.assertEqual([(c.nombre, c.unidad, c.nivel) for c in carreras], [
            ("Contador Público", "Facultad de Ciencias Económicas", "Grado"),
            ("Tecnicatura en Gestión Empresarial", "Facultad de Ciencias Económicas", "Pregrado"),
            ("Abogacía", "Facultad de Ciencias Humanas", "Grado"),
        ])
        self.assertEqual(carreras[2].url, "https://www.hum.unrc.edu.ar/abogacia/")


class SedesDeLaGuia(unittest.TestCase):
    def test_una_carrera_una_vez_y_una_oferta_por_sede(self):
        from rumbo_scraper.database.carreras_de_guias import sedes_de, unicas
        from rumbo_scraper.parsers.unc import CarreraDeLaGuia

        entradas = [
            CarreraDeLaGuia("Profesorado Universitario de Biología", "", "Instituto", "u/bv", "Grado",
                            "Sede Regional Bell Ville"),
            CarreraDeLaGuia("Tecnicatura Universitaria en Diseño Gráfico", "Facultad de Arte y Diseño",
                            "Facultad", "u/cba", "Pregrado", "Córdoba Capital"),
            CarreraDeLaGuia("Tecnicatura Universitaria en Diseño Gráfico", "", "Instituto", "u/vd",
                            "Pregrado", "Sede Regional Villa Dolores"),
        ]
        self.assertEqual([(c.nombre, c.unidad) for c in unicas(entradas)], [
            ("Profesorado Universitario de Biología", ""),
            ("Tecnicatura Universitaria en Diseño Gráfico", "Facultad de Arte y Diseño")])
        sedes = sedes_de(entradas)
        self.assertEqual(sorted(sedes[next(k for k in sedes if "grafico" in k)].items()),
                         [("Córdoba Capital", "u/cba"), ("Sede Regional Villa Dolores", "u/vd")])


PLAN_FCEFYN = """
<main>
<a href="/carrera/plan-de-estudios-2005/">Plan de estudios 2005</a>
<a href="/carrera/plan-de-estudios-2025-/">Plan de estudios 2025</a>
<p>Nivelación</p><p>(10-04050) Ambientación Universitaria</p>
<p>Primer año</p><p>Primer cuatrimestre</p>
<p>(10-09800) Fundamentos de Programación</p><p>(10-04053) Análisis Matemático 1</p>
<p>Segundo año</p><p>(10-09803) Programación Avanzada</p>
<p>Compartir</p><p>(10-99999) Algo del pie</p>
</main>
"""


class PlanDeIngenieriaUNC(unittest.TestCase):
    def test_el_plan_mas_nuevo_por_anio_sin_la_nivelacion(self):
        from rumbo_scraper.parsers.unc import leer_plan_fcefyn, plan_mas_nuevo

        self.assertEqual(plan_mas_nuevo(PLAN_FCEFYN, "https://fcefyn.unc.edu.ar/x/"),
                         "https://fcefyn.unc.edu.ar/carrera/plan-de-estudios-2025-/")
        self.assertEqual(leer_plan_fcefyn(PLAN_FCEFYN), [
            ("Fundamentos de Programación", 1), ("Análisis Matemático 1", 1),
            ("Programación Avanzada", 2)])
