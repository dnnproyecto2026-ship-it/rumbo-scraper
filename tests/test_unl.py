"""Tests for the careers and plans read off the UNL's catalogue."""

import unittest

from rumbo_scraper.parsers.unl import leer_plan, leer_unidad

UNIDAD = """
<a title="Centro Universitario / Reconquista-Avellaneda" href="x">CURA</a>
<div class="col-md-12 cabecera_nivel_carrera">Pregrado</div>
<div class="text_ua_box"><p><strong>CURA </strong>- Reconquista</p>
<p class="titulo_ua"><a href="https://www.unl.edu.ar/carreras/tecnicatura-x/?ua_id=" class="linko-carrera"> Tecnicatura Universitaria en Tecnología de Alimentos</a></p></div>
<div class="col-md-12 cabecera_nivel_carrera">Grado</div>
<div class="text_ua_box"><p><strong>CURA </strong>- Reconquista</p>
<p class="titulo_ua"><a href="https://www.unl.edu.ar/carreras/ciclo-de-licenciatura-en-alimentos/" class="linko-carrera"> Licenciatura en Ciencia y Tecnología de los Alimentos</a></p></div>
<div class="text_ua_box"><p><strong>CURA </strong>- Reconquista</p>
<p class="titulo_ua"><a href="https://www.unl.edu.ar/carreras/ciclo-inicial/" class="linko-carrera"> Trayecto Curricular Inicial de Ingeniería Agronómica</a></p></div>
<div class="col-md-12 cabecera_nivel_carrera">Posgrado</div>
<div class="text_ua_box"><p><strong>CURA </strong>- Reconquista</p>
<p class="titulo_ua"><a href="https://www.unl.edu.ar/carreras/maestria/" class="linko-carrera"> Maestría en Algo</a></p></div>
"""

CARRERA = """
<main><h1>Ingeniería en Informática</h1><p>DURACIÓN: 5 años</p>
<p>plan de estudios</p><p>CICLO INICIAL</p><p>•Matemática Básica</p><p>•Fundamentos de Programación</p>
<p>CICLO SUPERIOR</p><p>•Electrónica Digital</p>
<p>Además de las asignaturas mencionadas, se debe aprobar Acreditación de Inglés.</p><p>•Otra cosa</p></main>
"""


class CatalogoDeLaUNL(unittest.TestCase):
    def test_carreras_de_una_unidad_sin_ciclos_trayectos_ni_posgrados(self):
        carreras = leer_unidad(UNIDAD, "https://www.unl.edu.ar/propuesta-academica/", "CURA")
        self.assertEqual([(c.nombre, c.unidad, c.tipo_unidad, c.nivel, c.sede) for c in carreras], [
            ("Tecnicatura Universitaria en Tecnología de Alimentos",
             "Centro Universitario Reconquista-Avellaneda", "Centro", "Pregrado", "Reconquista")])
        self.assertEqual(carreras[0].url, "https://www.unl.edu.ar/carreras/tecnicatura-x/")

    def test_el_plan_son_las_vinetas_bajo_plan_de_estudios(self):
        self.assertEqual(leer_plan(CARRERA),
                         ["Matemática Básica", "Fundamentos de Programación", "Electrónica Digital"])


UNCUYO = """
<div class="card card-estudio"><div class="card-body"><h3 class="card-title">
<a href="https://www.uncuyo.edu.ar/estudios/carrera/quirofano"><span class="nombre_corto">Tecnicatura en Quirófano</span></a></h3>
<p class="d-none"><span class="nombre">Tecnicatura Universitaria en Quirófano</span></p></div>
<div class="card-footer"><span class="facultad">Cs. Médicas</span></div></div>
<div class="card card-estudio"><div class="card-body"><h3 class="card-title">
<a href="https://www.uncuyo.edu.ar/estudios/carrera/higiene"><span class="nombre_corto">Licenciatura en Higiene y Seguridad en el Trabajo</span></a></h3>
<p class="d-none"><span class="nombre">Ciclo de Licenciatura en Higiene y Seguridad en el Trabajo</span></p></div>
<div class="card-footer"><span class="facultad">Ingeniería</span></div></div>
<div class="card card-estudio"><div class="card-body"><h3 class="card-title">
<a href="https://www.uncuyo.edu.ar/estudios/carrera/fisica"><span class="nombre_corto">Licenciatura en Física</span></a></h3></div>
<div class="card-footer"><span class="facultad">Inst. Balseiro</span></div></div>
"""


class CatalogoDeLaUNCuyo(unittest.TestCase):
    def test_nombre_oficial_unidad_completa_y_sin_ciclos(self):
        from rumbo_scraper.parsers.uncuyo import leer_catalogo

        carreras = leer_catalogo(UNCUYO)
        self.assertEqual([(c.nombre, c.unidad, c.tipo_unidad, c.nivel) for c in carreras], [
            ("Tecnicatura Universitaria en Quirófano", "Facultad de Ciencias Médicas", "Facultad", "Pregrado"),
            ("Licenciatura en Física", "Instituto Balseiro", "Instituto", "Grado")])


PLAN_UNCUYO = """
<main><p>¿Cuál es la duración de la carrera?</p><p>La carrera tiene una duración de cinco años.</p>
<p>Plan de estudios:</p><p>Primer Año</p><p>Primer Semestre</p><p>Álgebra</p><p>Análisis Matemático I</p>
<p>Segundo Semestre</p><p>Física I</p><p>Quinta año</p><p>Primer Semestre</p><p>Gestión de la Calidad</p>
<p>Al finalizar la carrera obtendrás el título de:</p><p>Ingeniero/a Industrial</p></main>
"""


class PlanDeLaUNCuyo(unittest.TestCase):
    def test_por_anio_hasta_el_titulo(self):
        from rumbo_scraper.parsers.uncuyo import leer_plan

        self.assertEqual(leer_plan(PLAN_UNCUYO), [
            ("Álgebra", 1), ("Análisis Matemático I", 1), ("Física I", 1), ("Gestión de la Calidad", 5)])


UNT = """
<html><head><title>Facultad de Filosofía y Letras – Expo UNT</title></head><body>
<a href="http://filo.unt.edu.ar/letras/">Licenciatura en Letras - 5 Años</a>
<a href="http://filo.unt.edu.ar/historia/">Licenciatura en Historia- 5 Años</a>
<a href="http://filo.unt.edu.ar/ciencias-economicas/">Profesorado en Ciencias Económicas - 2 Años</a>
<a href="http://filo.unt.edu.ar/tec/">Tecnicatura en Algo - 2 años y medio</a>
<a href="http://filo.unt.edu.ar/">Contacto</a></body></html>
"""


class ExpoUNT(unittest.TestCase):
    def test_carreras_con_su_duracion_sin_ciclos_cortos(self):
        from rumbo_scraper.parsers.unt import leer_unidad

        carreras = leer_unidad(UNT, "https://www.unt.edu.ar/expount/x/")
        self.assertEqual([(c.nombre, c.unidad, c.nivel, c.duracion) for c in carreras], [
            ("Licenciatura en Letras", "Facultad de Filosofía y Letras", "Grado", 5.0),
            ("Licenciatura en Historia", "Facultad de Filosofía y Letras", "Grado", 5.0),
            ("Tecnicatura en Algo", "Facultad de Filosofía y Letras", "Pregrado", 2.5)])


UNR = """
<main><h2 class="elementor-heading-title">Ciencias Agrarias</h2>
<div class="elementor-toggle-item"><div class="elementor-tab-title"><a class="elementor-toggle-title">Ingeniería Agronómica</a></div>
<div class="elementor-tab-content"><p><a href="https://fcagr.unr.edu.ar/plan/">Plan de Estudios</a><br/>Duración: 5 años<br/>Campo Experimental – C.C. 14 – (2123) Zavalla<br/><a href="https://fcagr.unr.edu.ar/">https://fcagr.unr.edu.ar/</a></p></div></div>
<h2 class="elementor-heading-title">Ciencias Económicas y Estadística</h2>
<div class="elementor-toggle-item"><div class="elementor-tab-title"><a class="elementor-toggle-title">Contador Público​</a></div>
<div class="elementor-tab-content"><p><a href="https://www.fcecon.unr.edu.ar/cp">Plan de Estudios</a><br/>Duración: 5 años<br/>Bv Oroño 1261</p></div></div></main>
"""


class GuiaDeLaUNR(unittest.TestCase):
    def test_carrera_facultad_duracion_y_localidad(self):
        from rumbo_scraper.parsers.unr import leer_guia

        carreras = leer_guia(UNR)
        self.assertEqual([(c.nombre, c.unidad, c.sede, c.duracion, c.url) for c in carreras], [
            ("Ingeniería Agronómica", "Facultad de Ciencias Agrarias", "Zavalla", 5.0,
             "https://fcagr.unr.edu.ar/plan/"),
            ("Contador Público", "Facultad de Ciencias Económicas y Estadística", "Rosario", 5.0,
             "https://www.fcecon.unr.edu.ar/cp")])
