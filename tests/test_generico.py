"""Tests for the reader that works on any university."""

import unittest

from rumbo_scraper.catalogo import POR_CLAVE, UNIVERSIDADES, buscar
from rumbo_scraper.parsers import generico


class ReconocerUnPrograma(unittest.TestCase):
    def test_el_titulo_dice_el_nivel(self):
        for nombre, nivel in (
            ("Licenciatura en Psicología", "Grado"),
            ("Ingeniería Industrial", "Grado"),
            ("Tecnicatura Universitaria en Química", "Pregrado"),
            ("Maestría en Economía", "Posgrado"),
            ("Doctorado en Ciencias Sociales", "Posgrado"),
            ("Especialización en Criminología", "Posgrado"),
            ("Contador Público", "Grado"),
        ):
            with self.subTest(nombre=nombre):
                self.assertEqual(generico.clasificar(nombre)[0], nivel)

    def test_el_posgrado_declara_su_tipo(self):
        self.assertEqual(generico.clasificar("Maestría en Finanzas")[1], "Maestría")
        self.assertEqual(generico.clasificar("Doctorado en Física")[1], "Doctorado")
        self.assertIsNone(generico.clasificar("Licenciatura en Letras")[1])

    def test_el_indice_de_las_carreras_no_es_una_carrera(self):
        for nombre in ("Licenciatura", "Profesorado", "profesorados",
                       "Tecnicatura universitaria", "Licenciaturas",
                       "Carreras de Grado", "Oferta académica",
                       "Inscripción a Licenciatura en Economía"):
            with self.subTest(nombre=nombre):
                self.assertFalse(generico.es_programa(nombre))

    def test_una_noticia_sobre_una_carrera_no_es_una_carrera(self):
        self.assertFalse(generico.es_programa(
            "Se abre la inscripción a la Licenciatura en Enfermería"))
        self.assertFalse(generico.es_programa(
            "Licenciatura en Educación: Actividad especial de grado"))

    def test_el_encabezado_gana_al_titulo_de_la_ventana(self):
        html = ("<html><head><title>Inicio | UNQ</title></head>"
                "<body><h1>Licenciatura en Biotecnología</h1></body></html>")
        self.assertEqual(generico.encabezado(html), "Licenciatura en Biotecnología")

    def test_el_titulo_de_la_ventana_sirve_sin_encabezado(self):
        html = ("<html><head><title>Ingeniería en Alimentos - UNQ</title></head>"
                "<body><p>texto</p></body></html>")
        self.assertEqual(generico.encabezado(html), "Ingeniería en Alimentos")


class LeerLosDatos(unittest.TestCase):
    def test_los_datos_separados_por_salto_de_linea(self):
        html = ("<h1>Licenciatura en Biotecnología</h1>"
                "<h4>Modalidad: Presencial<br/>Nivel: Grado<br/>"
                "Título: Licenciado<br/>Unidad Académica: Ciencia y Tecnología</h4>")
        facts = generico.leer_datos(html)
        self.assertEqual(facts["modalidad"], "Presencial")
        self.assertEqual(facts["nivel"], "Grado")
        self.assertEqual(facts["facultad"], "Ciencia y Tecnología")

    def test_la_tabla_de_dos_columnas(self):
        html = ("<h1>Ingeniería Civil</h1><table><tr><th>Duración</th>"
                "<td>5 años</td></tr><tr><th>Modalidad</th><td>Presencial</td>"
                "</tr></table>")
        facts = generico.leer_datos(html)
        self.assertEqual(generico.duracion_anios(facts["duracion"]), 5.0)

    def test_el_cuerpo_no_se_borra_por_su_clase(self):
        # WordPress writes "sidebar" into the class of the body itself, and an
        # unguarded sweep by class takes the whole page with it.
        html = ('<body class="nv-sidebar-full-width"><h1>Licenciatura en Letras'
                '</h1><p>Duración: 4 años</p></body>')
        self.assertEqual(generico.leer_datos(html).get("duracion"), "4 años")

    def test_la_miga_de_pan_no_es_una_fecha(self):
        html = ('<h1>Licenciatura en Letras</h1>'
                '<div class="breadcrumbs">Inicio » Carreras</div>')
        self.assertNotIn("inicio", generico.leer_datos(html))

    def test_la_duracion_en_cuatrimestres(self):
        self.assertEqual(generico.duracion_anios("8 cuatrimestres"), 4.0)
        self.assertEqual(generico.duracion_meses("4 cuatrimestres"), 24)

    def test_la_duracion_imposible_no_se_lee(self):
        self.assertIsNone(generico.duracion_anios("Resolución 2019 años"))

    def test_la_modalidad(self):
        self.assertEqual(generico.modalidad("Presencial"), "Presencial")
        self.assertEqual(generico.modalidad("A distancia"), "Virtual")
        self.assertEqual(generico.modalidad("Semipresencial"), "Híbrida")
        self.assertIsNone(generico.modalidad("Anual"))

    def test_la_resolucion(self):
        self.assertEqual(
            generico.resolucion("cuenta con aprobación por la Resolución Nº 665/19"),
            "665/19")
        self.assertIsNone(generico.resolucion("Presencial"))


class LeerLasPersonas(unittest.TestCase):
    def test_una_directora_no_es_la_rectora(self):
        # "Directora" holds "rector" inside it.
        self.assertEqual(generico.cargo_de("Directora de la Licenciatura"), "Académico")
        self.assertEqual(generico.cargo_de("Rectora"), "Institucional")

    def test_el_vicerrector_se_escribe_con_doble_erre(self):
        self.assertEqual(generico.cargo_de("Vicerrector Académico"), "Institucional")

    def test_la_persona_y_su_cargo(self):
        html = ("<h1>Licenciatura en Biotecnología</h1><p>Autoridades:</p>"
                "<p>Natalia Lorena Rojas – Directora de la Licenciatura</p>")
        people = generico.leer_autoridades(html)
        self.assertEqual(people[0]["nombre"], "Natalia Lorena Rojas")
        self.assertEqual(people[0]["tipo"], "Académico")

    def test_dos_palabras_con_guion_no_son_una_persona(self):
        html = "<h1>Licenciatura en Letras</h1><p>Sede Bernal – Buenos Aires</p>"
        self.assertEqual(generico.leer_autoridades(html), [])


class LeerLosContactos(unittest.TestCase):
    def test_solo_las_direcciones_de_la_universidad(self):
        html = ("<h1>Licenciatura en Letras</h1><p>informes@unq.edu.ar</p>"
                "<p>congreso2024@gmail.com</p>")
        found = generico.leer_contactos(html, ("unq.edu.ar",))
        self.assertEqual([row["usuario_o_direccion"] for row in found],
                         ["informes@unq.edu.ar"])


class LeerElPlan(unittest.TestCase):
    def test_el_ano_y_sus_materias(self):
        html = ("<h3>Primer año</h3><ul><li>Álgebra</li><li>Análisis Matemático I"
                "</li><li>Química General</li></ul>"
                "<h3>Segundo año</h3><ul><li>Física I</li><li>Programación</li></ul>")
        plan = generico.leer_plan(html)
        self.assertEqual(len(plan), 5)
        self.assertEqual(plan[0], {"nombre": "Álgebra", "anio": 1})
        self.assertEqual(plan[-1]["anio"], 2)

    def test_un_plan_sin_anos_no_se_lee(self):
        # Without the year the rows cannot be told from any other list.
        html = "<ul><li>Álgebra</li><li>Física</li><li>Química</li></ul>"
        self.assertEqual(generico.leer_plan(html), [])

    def test_el_encabezado_de_la_columna_no_es_una_materia(self):
        for texto in ("Asignatura", "Carga horaria", "Total", "Código",
                      "Correlativas", "Año"):
            with self.subTest(texto=texto):
                self.assertFalse(generico.es_materia(texto))

    def test_el_ano_escrito_de_varias_formas(self):
        for texto in ("Primer año", "1er Año", "Año 1", "PRIMER AÑO", "1° año"):
            with self.subTest(texto=texto):
                self.assertEqual(generico.anio_de(texto), 1)


class ElCatalogo(unittest.TestCase):
    def test_cada_universidad_se_nombra_una_sola_vez(self):
        claves = [u.nombre_corto.lower() for u in UNIVERSIDADES]
        self.assertEqual(len(claves), len(set(claves)))
        self.assertEqual(len(POR_CLAVE), len(UNIVERSIDADES))

    def test_el_tipo_de_gestion_es_el_del_esquema(self):
        for universidad in UNIVERSIDADES:
            with self.subTest(universidad=universidad.nombre_corto):
                self.assertIn(universidad.tipo_gestion, {"Privada", "Estatal"})

    def test_el_dominio_coincide_con_el_sitio(self):
        for universidad in UNIVERSIDADES:
            with self.subTest(universidad=universidad.nombre_corto):
                self.assertIn(universidad.dominio, universidad.sitio_web)

    def test_se_busca_por_sigla(self):
        self.assertEqual(buscar("UNQ").nombre_corto, "UNQ")
        with self.assertRaises(SystemExit):
            buscar("no-existe")


if __name__ == "__main__":
    unittest.main()


class ElRuidoDeUnSitio(unittest.TestCase):
    def test_una_publicidad_no_es_una_carrera(self):
        self.assertFalse(generico.es_programa("¡Estudiá Ingeniería en la UNAHUR en 2018!"))

    def test_una_noticia_sobre_sus_alumnos_no_es_una_carrera(self):
        self.assertFalse(generico.es_programa(
            "Estudiantes de Ingeniería Metalúrgica visitan Tenaris"))
        self.assertFalse(generico.es_programa(
            "Docentes de la Licenciatura en Letras ganaron un premio"))

    def test_dos_cohortes_son_un_solo_programa(self):
        self.assertEqual(generico.sin_cohorte("Doctorado en Educación: cohorte 2025"),
                         "Doctorado en Educación")
        self.assertEqual(
            generico.sin_cohorte("Especialización en Alfabetización: Inscripción 2025"),
            "Especialización en Alfabetización")

    def test_un_curso_de_extension_no_es_una_carrera(self):
        # The subject of a degree also turns up inside the name of a course.
        self.assertFalse(generico.es_programa("Agente de Propaganda Médica"))
        self.assertFalse(generico.es_programa("Auxiliar de Farmacia"))
        self.assertTrue(generico.es_programa("Medicina Veterinaria"))

    def test_una_secretaria_no_es_una_unidad_academica(self):
        self.assertIsNone(generico.nombre_facultad("Secretaría de Extensión"))
        self.assertEqual(generico.nombre_facultad("Ciencia y Tecnología"),
                         "Ciencia y Tecnología")

    def test_el_plan_no_sigue_hasta_el_pie_de_la_pagina(self):
        html = ("<h3>Primer año</h3><p>Álgebra</p><p>Física</p><p>Química</p>"
                "<p>Biología</p><p>Contacto</p><p>Sedes</p><p>Suscribite:</p>")
        nombres = [row["nombre"] for row in generico.leer_plan(html)]
        self.assertEqual(nombres, ["Álgebra", "Física", "Química", "Biología"])

    def test_el_plan_escrito_con_saltos_de_linea(self):
        html = ("<p>PRIMER AÑO<br/>• Álgebra<br/>• Química I<br/>• Física I</p>"
                "<p>SEGUNDO AÑO<br/>• Análisis Matemático<br/>• Física II</p>")
        plan = generico.leer_plan(html)
        self.assertEqual(len(plan), 5)
        self.assertEqual(plan[0], {"nombre": "Álgebra", "anio": 1})

    def test_un_bloque_desbordado_invalida_el_plan(self):
        # More than thirty subjects in one year means the reader walked past
        # the end of the plan, and nothing it read can be trusted.
        html = "<h3>Primer año</h3>" + "".join(
            f"<p>Materia número {n}</p>" for n in range(40))
        self.assertEqual(generico.leer_plan(html), [])

    def test_se_siguen_los_subdominios_de_la_universidad(self):
        self.assertTrue(generico.es_del_dominio(
            "https://info.unlp.edu.ar/carreras/", ("unlp.edu.ar",)))
        self.assertFalse(generico.es_del_dominio(
            "https://unlp.edu.ar.otro.com/x", ("unlp.edu.ar",)))


class ElRuidoQueQuedaba(unittest.TestCase):
    def test_una_unidad_academica_no_es_una_carrera(self):
        for nombre in ("Instituto de Ingeniería y Agronomía",
                       "Departamento de Ciencias Sociales",
                       "Escuela de Enfermería"):
            with self.subTest(nombre=nombre):
                self.assertFalse(generico.es_programa(nombre))

    def test_el_verbo_se_conjuga(self):
        # A stem with a bare boundary after it matches none of the forms a
        # headline actually uses.
        for nombre in ("Comenzó la Diplomatura Superior en Políticas",
                       "Comenzaron las clases de la Diplomatura en Educación",
                       "Se presentaron las Licenciaturas nuevas"):
            with self.subTest(nombre=nombre):
                self.assertFalse(generico.es_programa(nombre))

    def test_una_seccion_de_la_carrera_no_es_otra_carrera(self):
        self.assertEqual(generico.sin_cohorte("Ingeniería Química: Cuerpo Académico"),
                         "Ingeniería Química")
        self.assertEqual(generico.sin_cohorte("Abogacía - Plan de Estudios"), "Abogacía")

    def test_un_encabezado_de_periodo_no_es_una_materia(self):
        for texto in ("PRIMER CUATRIMESTRE", "Segundo Cuatrimestre", "Tercer Año"):
            with self.subTest(texto=texto):
                self.assertFalse(generico.es_materia(texto))

    def test_el_pedazo_de_una_frase_no_es_una_materia(self):
        for texto in (", se articula con la", "de la Universidad Nacional",
                      "y también con el programa"):
            with self.subTest(texto=texto):
                self.assertFalse(generico.es_materia(texto))


class LasPaginasVecinas(unittest.TestCase):
    def test_la_lista_de_materias_no_es_otra_carrera(self):
        for nombre in ("Asignaturas de la Tecnicatura en Comunicación Popular",
                       "Materias de la Licenciatura en Letras",
                       "Correlatividades de Abogacía"):
            with self.subTest(nombre=nombre):
                self.assertFalse(generico.es_programa(nombre))
