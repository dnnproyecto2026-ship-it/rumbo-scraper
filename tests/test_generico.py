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


class LaVidaUniversitaria(unittest.TestCase):
    def test_la_invitacion_no_es_una_actividad(self):
        from rumbo_scraper.parsers import vida
        html = ("<h3>Te proponemos actividades deportivas porque:</h3>"
                "<h3>Formate y sé parte de la evolución del deporte</h3>"
                "<h3>¿Por qué hacer un intercambio?</h3>"
                "<h3>Departamento de Deportes UP</h3>")
        nombres = [row["titulo"]
                   for row in vida.read_items(html, "actividades_extracurriculares")]
        self.assertEqual(nombres, ["Departamento de Deportes UP"])

    def test_la_etiqueta_de_la_seccion_no_es_una_actividad(self):
        # "Deportes" on its own is the entry of the menu that opens the page.
        from rumbo_scraper.parsers import vida
        html = "<h3>Deportes</h3><h3>Becas</h3><h3>Vida universitaria</h3>"
        self.assertEqual(vida.read_items(html, "actividades_extracurriculares"), [])

    def test_una_noticia_no_es_una_actividad(self):
        from rumbo_scraper.parsers import vida
        html = ("<h3>La UNLP consolida el acceso a actividades deportivas</h3>"
                "<h3>Requisitos médicos | Deportes 2025</h3>")
        self.assertEqual(vida.read_items(html, "actividades_extracurriculares"), [])

    def test_la_vineta_no_forma_parte_del_nombre(self):
        from rumbo_scraper.parsers import vida
        html = "<h3>— Programa de Ayudas Económicas</h3>"
        nombres = [row["titulo"] for row in vida.read_items(html, "becas")]
        self.assertEqual(nombres, ["Programa de Ayudas Económicas"])


class LasMateriasQueTienenPaginaPropia(unittest.TestCase):
    def test_una_materia_no_es_una_carrera(self):
        # A university that publishes its plans gives each subject a page,
        # and a subject carries the name of a degree inside it.
        for nombre in ("Arquitectura de Computadoras", "Psicología del Aprendizaje",
                       "Ingeniería del Software II",
                       "Física para Licenciatura en ciencias de la computación"):
            with self.subTest(nombre=nombre):
                self.assertFalse(generico.es_programa(nombre))

    def test_el_titulo_que_se_nombra_por_su_materia_sigue_valiendo(self):
        for nombre in ("Medicina", "Medicina Veterinaria", "Arquitectura",
                       "Arquitectura Naval", "Diseño de Indumentaria"):
            with self.subTest(nombre=nombre):
                self.assertTrue(generico.es_programa(nombre))

    def test_el_codigo_interno_no_forma_parte_del_nombre(self):
        self.assertEqual(generico.sin_cohorte("(10-09218) Ingeniería en Rehabilitación"),
                         "Ingeniería en Rehabilitación")

    def test_el_tramite_que_crea_una_carrera_no_es_la_carrera(self):
        self.assertFalse(generico.es_programa(
            "Ordenanza nº 290/16 y Anexo Diplomatura universitaria"))
        self.assertFalse(generico.es_programa("diplomatura archivos"))


class ElIndiceDeCarreras(unittest.TestCase):
    def test_se_reconoce_la_pagina_que_lista_las_carreras(self):
        for url in ("https://unpaz.edu.ar/carreras",
                    "https://x.edu.ar/oferta-academica/",
                    "https://x.edu.ar/posgrado"):
            with self.subTest(url=url):
                self.assertTrue(generico.es_el_indice(url))

    def test_la_carrera_no_es_el_indice(self):
        self.assertFalse(generico.es_el_indice("https://x.edu.ar/carreras/abogacia"))


class LaPublicidadDeLaUniversidad(unittest.TestCase):
    def test_una_pregunta_no_es_una_carrera(self):
        self.assertFalse(generico.es_programa("¿Por qué Ingeniería en la Católica?"))

    def test_la_tienda_no_es_una_carrera(self):
        self.assertFalse(generico.es_programa("Comprar Ingeniería en LibrosUCC"))


class CuandoHaceFaltaUnNavegador(unittest.TestCase):
    def test_una_cascara_vacia_no_tiene_contenido(self):
        from rumbo_scraper.spiders.generico import _tiene_contenido
        self.assertFalse(_tiene_contenido(
            '<html><body><div id="root"></div><script src="app.js"></script></body></html>'))

    def test_una_pagina_servida_entera_si(self):
        from rumbo_scraper.spiders.generico import _tiene_contenido
        pagina = ("<html><body>" + "<p>texto de la carrera</p>" * 300
                  + "".join(f'<a href="/x{n}">x</a>' for n in range(8)) + "</body></html>")
        self.assertTrue(_tiene_contenido(pagina))


class ElCatalogoEnLaConsulta(unittest.TestCase):
    def test_la_consulta_tambien_dice_de_que_es_la_pagina(self):
        # Moreno publishes its catalogue where the path says nothing.
        url = "https://www.unm.edu.ar/?oferta-academica=carreras-de-pregrado-y-grado"
        self.assertTrue(generico.parece_catalogo(url))
        self.assertTrue(generico.es_el_indice(url))

    def test_una_noticia_sigue_sin_ser_catalogo(self):
        self.assertFalse(generico.parece_catalogo("https://x.edu.ar/noticias/algo"))


class UnaPaginaQueSoloRedirige(unittest.TestCase):
    def test_se_sigue_la_mudanza_por_javascript(self):
        html = ('<html><body><script>window.location = '
                '"https://undav.edu.ar/index.php"</script></body></html>')
        self.assertEqual(generico.se_mudo_a(html, "https://undav.edu.ar"),
                         "https://undav.edu.ar/index.php")

    def test_se_sigue_la_mudanza_por_meta(self):
        self.assertEqual(
            generico.se_mudo_a('<meta http-equiv="refresh" content="0; url=/inicio">',
                               "https://x.edu.ar"),
            "https://x.edu.ar/inicio")

    def test_una_pagina_con_contenido_no_es_una_mudanza(self):
        # The instruction appears inside pages that also say something; only
        # a page that says nothing else is following it.
        self.assertIsNone(generico.se_mudo_a("<html>" + "x" * 9000 + "</html>",
                                             "https://x.edu.ar"))


class UnSitioQueNombraTodoIgual(unittest.TestCase):
    def test_la_carrera_se_nombra_por_el_enlace_que_lleva_a_ella(self):
        # Avellaneda heads every page with the name of the university, so the
        # name of the career is written only in the menu entry that opens it.
        pagina = ("<html><body><h1>Universidad Nacional de Avellaneda</h1>"
                  + "<p>texto de la carrera</p>" * 200 + "</body></html>")
        programa = generico.leer_programa_por_etiqueta(
            pagina, "https://undav.edu.ar/index.php?idcateg=297", "Abogacía")
        self.assertIsNotNone(programa)
        self.assertEqual(programa.nombre, "Abogacía")
        self.assertEqual(programa.nivel, "Grado")

    def test_no_se_usa_el_enlace_si_la_pagina_se_nombra_sola(self):
        pagina = "<h1>Licenciatura en Letras</h1>" + "<p>x</p>" * 200
        self.assertIsNone(generico.leer_programa_por_etiqueta(
            pagina, "https://u.edu.ar/x", "Abogacía"))

    def test_un_menu_no_alcanza_para_ser_una_carrera(self):
        self.assertIsNone(generico.leer_programa_por_etiqueta(
            "<h1>Universidad</h1><p>corto</p>", "https://u.edu.ar/x", "Abogacía"))


class UnaOfertaNoSeEscribeDosVeces(unittest.TestCase):
    """The offer is identified by its career and its campus.

    Upserting on the modality as well looks right and is not: a university
    that does not publish a modality leaves the column null, and in Postgres
    a null never equals another null, so the conflict never fires.
    """

    class _Tabla:
        def __init__(self, almacen): self.almacen = almacen; self._filtros = {}
        def select(self, *_a, **_k): return self
        def eq(self, campo, valor): self._filtros[campo] = valor; return self
        def limit(self, _n): return self
        def insert(self, fila):
            fila = {**fila, "id": f"id{len(self.almacen)}"}
            self.almacen.append(fila); self._resultado = [fila]; return self
        def update(self, fila):
            for guardada in self.almacen:
                if guardada["id"] == self._filtros.get("id"):
                    guardada.update(fila); self._resultado = [guardada]
            return self
        def execute(self):
            if hasattr(self, "_resultado"):
                salida, self._resultado = self._resultado, None
                return type("R", (), {"data": salida})()
            hallados = [f for f in self.almacen
                        if all(f.get(k) == v for k, v in self._filtros.items())]
            self._filtros = {}
            return type("R", (), {"data": hallados})()

    def test_la_misma_oferta_dos_veces_es_una_fila(self):
        from rumbo_scraper.database.load_utdt import _upsert_oferta
        almacen: list[dict] = []
        cliente = type("C", (), {"table": lambda _s, _t: UnaOfertaNoSeEscribeDosVeces._Tabla(almacen)})()
        fila = {"carrera_id": "c1", "sede_id": "s1", "modalidad": None, "activa": True}
        _upsert_oferta(cliente, fila)
        _upsert_oferta(cliente, fila)
        self.assertEqual(len(almacen), 1)


class ElPlanPublicadoComoDocumento(unittest.TestCase):
    def test_el_codigo_pegado_al_nombre_se_saca(self):
        from rumbo_scraper.parsers.generico import _limpiar_materia
        self.assertEqual(_limpiar_materia("ANALISIS MATEMATICO I04052"),
                         "ANALISIS MATEMATICO I")
        self.assertEqual(_limpiar_materia("Química II"), "Química II")

    def test_un_documento_sin_anos_no_es_un_plan(self):
        # The same reader pointed at a university's letterhead returns its
        # address and the names of its authorities as subjects.
        from rumbo_scraper.parsers import generico
        materias = generico.leer_plan_documento(b"", "Licenciatura", "Universidad")
        self.assertEqual(materias, [])


class ElArchivoDelPlan(unittest.TestCase):
    def test_el_nombre_del_archivo_separa_con_guiones(self):
        from rumbo_scraper.spiders.generico import _documento_del_plan
        html = ('<a href="/uploads/Ingenieria-Industrial-PLAN-DE-ESTUDIOS.pdf">'
                'Descargar</a>')
        self.assertEqual(
            _documento_del_plan(html, "https://www.unlam.edu.ar/x", ("unlam.edu.ar",)),
            "https://www.unlam.edu.ar/uploads/Ingenieria-Industrial-PLAN-DE-ESTUDIOS.pdf")

    def test_el_plan_estrategico_no_es_el_plan_de_una_carrera(self):
        from rumbo_scraper.spiders.generico import _documento_del_plan
        html = '<a href="/plan-estrategico-2022.pdf">Plan estratégico</a>'
        self.assertIsNone(
            _documento_del_plan(html, "https://u.edu.ar/x", ("u.edu.ar",)))


class LosConveniosDeIntercambio(unittest.TestCase):
    def test_se_lee_la_universidad_y_su_pais(self):
        from rumbo_scraper.parsers.convenios import leer_convenios
        html = ("<ul><li>Universidad de Salamanca (España)</li>"
                "<li>University of Toronto, Canadá</li></ul>")
        filas = leer_convenios(html, "https://u.edu.ar/x", "Universidad Nacional")
        self.assertEqual([(f["universidad_destino"], f["pais"]) for f in filas],
                         [("Universidad de Salamanca", "España"),
                          ("University of Toronto", "Canadá")])

    def test_el_pais_que_es_parte_del_nombre_no_se_corta(self):
        from rumbo_scraper.parsers.convenios import leer_convenios
        html = "<li>Universidad Católica del Uruguay</li>"
        filas = leer_convenios(html, "https://u.edu.ar/x", "Universidad Nacional")
        self.assertEqual(filas[0]["universidad_destino"],
                         "Universidad Católica del Uruguay")

    def test_sin_pais_no_hay_convenio(self):
        # A university named with no country is as likely to be a faculty of
        # the university publishing the page.
        from rumbo_scraper.parsers.convenios import leer_convenios
        html = "<li>Universidad Nacional de Quilmes</li>"
        self.assertEqual(leer_convenios(html, "https://u.edu.ar/x", "Otra"), [])


class LosConveniosDeIntercambio(unittest.TestCase):
    def test_la_universidad_y_su_pais(self):
        from rumbo_scraper.parsers.convenios import leer_convenios
        html = ("<ul><li>Universidad de Salamanca (España)</li>"
                "<li>Universidade de São Paulo - Brasil</li>"
                "<li>University of Toronto, Canadá</li></ul>"
                "<table><tr><td>Universidad de Bolonia</td><td>Italia</td></tr></table>")
        filas = leer_convenios(html, "u", "Universidad Nacional de Quilmes")
        self.assertEqual([(f["universidad_destino"], f["pais"]) for f in filas], [
            ("Universidad de Salamanca", "España"),
            ("Universidade de São Paulo", "Brasil"),
            ("University of Toronto", "Canadá"),
            ("Universidad de Bolonia", "Italia"),
        ])

    def test_sin_pais_no_es_un_convenio(self):
        # A university named without a country is as likely to be a faculty
        # of the one publishing the page.
        from rumbo_scraper.parsers.convenios import leer_convenios
        self.assertEqual(leer_convenios("<li>Universidad de Salamanca</li>", "u", "X"), [])

    def test_la_universidad_que_publica_no_es_su_propio_convenio(self):
        from rumbo_scraper.parsers.convenios import leer_convenios
        html = "<li>Universidad Nacional de Quilmes (Argentina)</li>"
        self.assertEqual(
            leer_convenios(html, "u", "Universidad Nacional de Quilmes"), [])

    def test_el_encabezado_de_la_lista_no_es_un_convenio(self):
        from rumbo_scraper.parsers.convenios import leer_convenios
        self.assertEqual(leer_convenios("<li>Universidades de destino - España</li>",
                                        "u", "X"), [])


class ElPaisDelConvenio(unittest.TestCase):
    def test_el_pais_repetido_en_el_nombre(self):
        from rumbo_scraper.parsers.convenios import leer_convenios
        filas = leer_convenios(
            "<li>Universidad Católica de Costa Rica (Costa Rica)</li>"
            "<li>Universidad Iberoamericana (UNIBE) - Paraguay</li>", "u", "X")
        self.assertEqual([f["universidad_destino"] for f in filas],
                         ["Universidad Católica de Costa Rica",
                          "Universidad Iberoamericana (UNIBE)"])

    def test_un_intercambio_es_con_el_exterior(self):
        from rumbo_scraper.parsers.convenios import leer_convenios
        self.assertEqual(leer_convenios(
            "<li>Universidad de Argentina en la región</li>", "u", "X"), [])


class UnaLecturaVaciaNoSeAplica(unittest.TestCase):
    """A reading that found nothing is a fact about the network.

    UNGS lost a hundred and forty-nine subjects and three hundred and
    forty-one contacts to six "Network is unreachable" errors: the guard that
    refuses to retire careers did not cover the tables that are rewritten
    whole.
    """

    def _vacio(self):
        from rumbo_scraper.contracts import SECTION_FIELDS, blank_record
        datos = {seccion: [] for seccion in SECTION_FIELDS}
        datos["universidades"] = [blank_record(
            "universidades", nombre_oficial="Universidad Nacional",
            nombre_corto="UN", tipo_gestion="Estatal",
            sitio_web="https://u.edu.ar")]
        return {"datos": datos, "fuente_principal": "https://u.edu.ar",
                "control_calidad": {"paginas_recorridas": 0}}

    def test_se_rechaza(self):
        from rumbo_scraper.database.load_generico import LecturaVacia, apply_dataset
        with self.assertRaises(LecturaVacia):
            apply_dataset(self._vacio(), client=object())


class CanalesDeLaUniversidadTest(unittest.TestCase):
    def test_mirrors_only_the_columns_the_university_filled(self):
        from rumbo_scraper.database.perfil_universidades import canales_de
        filas = canales_de({"id": "u1", "sitio_web": "https://www.uca.edu.ar",
                            "instagram": "https://instagram.com/ucaargentina",
                            "facebook": None, "mail_contacto": "  ",
                            "telefono_numero": "4338-0600"})
        self.assertEqual([f["canal"] for f in filas], ["Sitio Web", "Instagram"])
        self.assertTrue(all(f["facultad_id"] is None and f["universidad_id"] == "u1"
                            for f in filas))


class PlanesDelAdaptadorTest(unittest.TestCase):
    def test_takes_each_programme_once_with_the_page_its_adapter_recorded(self):
        from rumbo_scraper.database.planes_adaptador import programas_del_adaptador
        programas = programas_del_adaptador({"datos": {
            "ofertas": [
                {"carrera_nombre": "Economía", "url_oficial": "https://u.edu.ar/grado/eco"},
                {"carrera_nombre": "Economía", "url_oficial": "https://u.edu.ar/grado/eco"},
                {"carrera_nombre": "Sin página", "url_oficial": None},
            ],
            "posgrados": [{"nombre_programa": "Maestría en Finanzas",
                           "tipo_posgrado": "Maestría",
                           "url_oficial": "https://u.edu.ar/posgrado/mf"}],
        }})
        self.assertEqual([(p.nombre, p.nivel) for p in programas],
                         [("Economía", "Grado"), ("Maestría en Finanzas", "Posgrado")])


class NoEsUnProgramaTest(unittest.TestCase):
    def test_a_part_of_a_programme_a_council_minute_and_a_person_are_not_programmes(self):
        for nombre in ("Ingeniería Biomédica - Admisión",
                       "Licenciatura en Nutrición - Misión y Valores",
                       "Maestría en Preguntas Frecuentes",
                       "Licenciatura en Arte Conocé la carrera",
                       "Diplomatura Superior en Equidad en Salud – Cuerpo Directivo",
                       'RES 054 - 2012 "CS" CGA Maestría',
                       '2013 "CS" Modificar los alcances de la Licenciatura en Actividad Física',
                       "Emanuel Porcelli | Subsecretario de Maestrías"):
            self.assertFalse(generico.es_programa(nombre), nombre)

    def test_variants_and_degrees_in_teaching_stay_programmes(self):
        for nombre in ("Especialización en Formación de Docentes",
                       "Licenciatura en Administración - Modalidad a Distancia",
                       "Maestría en Dirección de Empresas",
                       "Tecnicatura en Secretariado Ejecutivo"):
            self.assertTrue(generico.es_programa(nombre), nombre)

    def test_the_cleanup_renames_a_programme_it_has_no_other_record_of(self):
        from rumbo_scraper.database.retirar_no_programas import motivo, nombre_limpio
        self.assertEqual(nombre_limpio("Contador Público Conocé la carrera", "seccion"),
                         "Contador Público")
        self.assertEqual(nombre_limpio("Ingeniería Biomédica - Admisión", "seccion"),
                         "Ingeniería Biomédica")
        self.assertIsNone(nombre_limpio("Maestría en Preguntas Frecuentes", "seccion"))
        self.assertEqual(motivo('RES 054 - 2012 "CS" CGA Maestría'), "resolucion")


class SedesTest(unittest.TestCase):
    def test_an_unnamed_address_is_named_after_its_street_not_as_the_main_campus(self):
        from rumbo_scraper.parsers.institucional import leer_sedes
        sedes = leer_sedes("<html><body><p>Av. Calchaquí 610, B1884 Berazategui</p>"
                           "<p>Av. Calchaquí 6200</p></body></html>", "u")
        self.assertEqual([s["nombre_sede"] for s in sedes],
                         ["Sede Av. Calchaquí 610", "Sede Av. Calchaquí 6200"])

    def test_counts_phones_and_error_pages_are_not_addresses(self):
        from rumbo_scraper.parsers.institucional import leer_sedes
        for linea in ("Alumnos 0800 555 1234", "Aulas con capacidad para 40",
                      "Error 404", "Mayores de 25", "Julio 2024, Buenos Aires"):
            self.assertEqual(leer_sedes(f"<html><body><p>{linea}</p></body></html>", "u"),
                             [], linea)

    def test_a_campus_without_a_number_and_a_footer_address_are_read(self):
        from rumbo_scraper.parsers.institucional import leer_sedes
        unc = leer_sedes("<html><body><p>Pabellón Argentina, Av. Haya de la Torre s/n, "
                         "Ciudad Universitaria</p></body></html>", "u")
        self.assertEqual((unc[0]["nombre_sede"], unc[0]["calle"], unc[0]["numero"]),
                         ("Pabellón Argentina", "Av. Haya de la Torre", None))
        unlp = leer_sedes("<html><body><p>Universidad Nacional de La Plata Av. 7 N° 776, "
                          "La Plata (CP 1900)</p></body></html>", "u")
        self.assertEqual((unlp[0]["calle"], unlp[0]["numero"]), ("Av. 7", "776"))


class UnidadesPorEnlaceTest(unittest.TestCase):
    def test_a_unit_named_by_its_subject_is_read_from_its_address(self):
        from rumbo_scraper.parsers.institucional import unidades_por_enlace
        html = ('<a href="/departamentos/humanidades-y-artes">Humanidades y Artes</a>'
                '<a href="https://x.edu.ar/carreras/escuela-superior-de-ciencias-de-la-salud">'
                'Ciencias de la Salud</a>'
                '<a href="/carreras/licenciatura-en-arte">Arte</a>'
                '<a href="/departamentos/alumnos">Alumnos</a>')
        self.assertEqual([u["nombre_facultad"] for u in unidades_por_enlace(html, "https://x.edu.ar")],
                         ["Departamento de Humanidades y Artes",
                          "Escuela Superior de Ciencias de la Salud"])
