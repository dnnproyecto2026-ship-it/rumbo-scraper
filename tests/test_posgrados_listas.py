"""Tests for the postgraduate programmes read off a university's list."""

import unittest

from rumbo_scraper.parsers.posgrados_listas import leer_lista, nombre_de_posgrado

PAGINA = "https://www.unx.edu.ar/posgrado/"
LISTA = """
<nav><a href="/maestria-menu">Maestría en Menú</a></nav>
<main>
<h2>Carreras de posgrado</h2>
<ul>
<li><a href="https://fca.unx.edu.ar/posgrado/doctorado-agro/">Doctorado en Ciencias Agrarias</a></li>
<li><a href="/maestria-datos">MAESTRÍA EN CIENCIA DE DATOS</a> - Acreditada CONEAU Cat. B</li>
<li>Especialización en Docencia Universitaria</li>
<li><a href="https://otra.org/x">Especialización en Gestión Pública</a></li>
<li><a href="https://fhu.unx.edu.ar/">Maestría en Derechos Humanos</a></li>
<li>Doctorado en Educación Especialización en Investigación Educativa</li>
<li><a href="/dipl">Diplomatura en Gestión Cultural</a></li>
<li><a href="/n1">Abierta la inscripción a la Maestría en Estadística</a></li>
<li><a href="/c1">Curso de posgrado en Bioeconomía</a></li>
</ul>
</main>
"""


class NombreDePosgrado(unittest.TestCase):
    def test_lee_el_tipo_y_quita_la_acreditacion(self):
        self.assertEqual(nombre_de_posgrado("Maestría en Ciencias Agrarias - Acreditada CONEAU Cat. A"),
                         ("Maestría en Ciencias Agrarias", "Maestría"))
        self.assertEqual(nombre_de_posgrado("Carrera de Especialización en Cirugía"),
                         ("Especialización en Cirugía", "Especialización"))

    def test_como_escribe_una_privada_la_maestria(self):
        self.assertEqual(nombre_de_posgrado("Magíster en Finanzas"), ("Maestría en Finanzas", "Maestría"))
        self.assertEqual(nombre_de_posgrado("MBA - Maestría en Dirección de Empresas"),
                         ("Maestría en Dirección de Empresas", "Maestría"))
        self.assertEqual(nombre_de_posgrado("MBA Executive Full Time")[1], "Maestría")
        self.assertEqual(nombre_de_posgrado("Master in Business Administration")[1], "Maestría")

    def test_la_fecha_de_inicio_en_el_enlace(self):
        self.assertEqual(nombre_de_posgrado("Especialización en Argumentación Jurídica 17 marzo")[0],
                         "Especialización en Argumentación Jurídica")

    def test_una_noticia_no_es_un_nombre(self):
        self.assertIsNone(nombre_de_posgrado("Abierta la inscripción al Doctorado en Física"))
        self.assertIsNone(nombre_de_posgrado("Defensa de tesis de la Maestría en Estadística"))

    def test_solo_las_tres_carreras_de_posgrado(self):
        self.assertIsNone(nombre_de_posgrado("Diplomatura en Gestión Cultural"))
        self.assertIsNone(nombre_de_posgrado("Posgrados en Salud"))
        self.assertIsNone(nombre_de_posgrado("Maestrías"))

    def test_dos_carreras_en_una_linea_es_la_primera(self):
        self.assertEqual(nombre_de_posgrado("Especialización en Bioinformática Especialista en Bioinformática"),
                         ("Especialización en Bioinformática", "Especialización"))


class LeerLista(unittest.TestCase):
    def setUp(self):
        self.leidos = {p.nombre: p for p in leer_lista(LISTA, PAGINA, ("unx.edu.ar",))}

    def test_lee_cada_carrera_una_vez(self):
        self.assertEqual(sorted(self.leidos), [
            "Doctorado en Ciencias Agrarias", "Doctorado en Educación",
            "Especialización en Docencia Universitaria", "Especialización en Gestión Pública",
            "Maestría en Ciencia de Datos", "Maestría en Derechos Humanos",
        ])

    def test_toma_el_enlace_propio_de_los_sitios_de_la_universidad(self):
        self.assertEqual(self.leidos["Doctorado en Ciencias Agrarias"].url,
                         "https://fca.unx.edu.ar/posgrado/doctorado-agro/")
        self.assertEqual(self.leidos["Maestría en Ciencia de Datos"].url,
                         "https://www.unx.edu.ar/maestria-datos")

    def test_sin_enlace_propio_queda_la_lista(self):
        for nombre in ("Especialización en Docencia Universitaria",
                       "Especialización en Gestión Pública",  # links off-site
                       "Maestría en Derechos Humanos"):  # links a home page
            self.assertEqual(self.leidos[nombre].url, PAGINA)


TARJETAS = """
<div class="card"><div class="card-subtitle">Maestría</div>
<h3 class="card-title"><a href="https://fad.unx.edu.ar/estudios/posgrado/192  ">Gestión del Diseño | MGD</a></h3>
<p>Esta carrera forma profesionales...</p></div>
<div class="card"><div class="card-subtitle">Especialización</div>
<h3 class="card-title"><a href="https://fcj.unx.edu.ar/p/7">8ª Cohorte de Derecho del Trabajo</a></h3></div>
<div class="card"><div class="card-subtitle">Doctorado</div>
<h3 class="card-title"><a href="https://unx.edu.ar/doc.pdf">Física</a></h3></div>
"""


class LeerTarjetas(unittest.TestCase):
    def test_el_tipo_y_el_tema_en_elementos_apartes(self):
        leidos = {p.nombre: p.url for p in leer_lista(TARJETAS, PAGINA, ("unx.edu.ar",))}
        self.assertEqual(leidos, {
            "Maestría en Gestión del Diseño": "https://fad.unx.edu.ar/estudios/posgrado/192",
            "Especialización en Derecho del Trabajo": "https://fcj.unx.edu.ar/p/7",
            "Doctorado en Física": PAGINA,  # a PDF is not a page
        })

    def test_la_docencia_sin_su_en(self):
        self.assertEqual(nombre_de_posgrado("Especialización Docencia en Educación Superior")[1], "Especialización")

    def test_la_descripcion_no_es_parte_del_nombre(self):
        self.assertIsNone(nombre_de_posgrado("Maestría Gestión del Diseño para los Desarrollos"))
        self.assertEqual(nombre_de_posgrado("Doctorado Interinstitucional en Educación")[1], "Doctorado")


class LoQueLaListaAgregaAlNombre(unittest.TestCase):
    def test_la_sede_y_la_facultad_entre_parentesis(self):
        for texto in ("Maestría en Gestión Pública (Sede Corrientes)",
                      "Maestría en Gestión Pública (FHAyCS | Sede Paraná)",
                      "Maestría en Gestión Pública (En conjunto con la Facultad de Humanidades)"):
            self.assertEqual(nombre_de_posgrado(texto)[0], "Maestría en Gestión Pública")
        self.assertEqual(nombre_de_posgrado("Especialización en Odontología Restauradora "
                                            "(Operatoria Dental y Biomateriales)")[0],
                         "Especialización en Odontología Restauradora (Operatoria Dental y Biomateriales)")

    def test_lo_que_dice_de_la_cursada(self):
        self.assertEqual(nombre_de_posgrado("Especialización en Historia Militar (Carrera a distancia)")[0],
                         "Especialización en Historia Militar")
        self.assertEqual(nombre_de_posgrado("Maestría en Estrategia (Formación militar)")[0],
                         "Maestría en Estrategia")
        self.assertEqual(nombre_de_posgrado("Maestría en Ciberdefensa | Ver sitio")[0],
                         "Maestría en Ciberdefensa")

    def test_un_nombre_a_los_gritos(self):
        self.assertEqual(nombre_de_posgrado("ESPECIALIZACIÓN EN Sindicatura Concursal")[0],
                         "Especialización en Sindicatura Concursal")
        self.assertEqual(nombre_de_posgrado("maestría en Gestión Pública")[0], "Maestría en Gestión Pública")
        self.assertEqual(nombre_de_posgrado("MAESTRÍA en en Agronegocios y Alimentos")[0],
                         "Maestría en Agronegocios y Alimentos")

    def test_la_lista_guardada_en_el_script(self):
        html = ("<script>const contenidos = {ingenieria: `<ul><li><a href='/c/3'>Maestría en "
                "Energía</a></li></ul>`};</script>")
        self.assertEqual([(p.nombre, p.url) for p in leer_lista(html, PAGINA, ("unx.edu.ar",))],
                         [("Maestría en Energía", "https://www.unx.edu.ar/c/3")])

    def test_los_temas_bajo_un_titulo_que_dice_el_tipo(self):
        html = ('<div id="r"><h4>Carrera de Especialización bajo modalidad de Residencia</h4>'
                '<strong>BÁSICAS</strong><a href="/x.pdf"><strong>- Anatomía Patológica</strong></a>'
                ' (RM N° 267/2018)<strong>- Cirugía General</strong><strong>**</strong></div>')
        self.assertEqual([p.nombre for p in leer_lista(html, PAGINA, ("unx.edu.ar",), "#r strong",
                                                         prefijo="Especialización en")],
                         ["Especialización en Anatomía Patológica", "Especialización en Cirugía General"])

    def test_dos_titulos_sobre_un_tema(self):
        html = '<h2>Especialización y Maestría en <b>Informática en Salud</b></h2>'
        self.assertEqual(sorted(p.nombre for p in leer_lista(html, PAGINA, ("unx.edu.ar",))),
                         ["Especialización en Informática en Salud", "Maestría en Informática en Salud"])

    def test_un_tipo_sobre_varios_temas(self):
        html = ('<div><div class="sub">Especialización</div><a class="it" href="/cirugia/"><span>Cirugía'
                '</span></a><a class="it" href="/endo/"><span>Endodoncia</span></a>'
                '<div class="sub">Maestría</div><a class="it" href="/sm/">Salud Mental</a></div>')
        self.assertEqual([(p.nombre, p.url) for p in leer_lista(html, PAGINA, ("unx.edu.ar",))], [
            ("Especialización en Cirugía", "https://www.unx.edu.ar/cirugia/"),
            ("Especialización en Endodoncia", "https://www.unx.edu.ar/endo/"),
            ("Maestría en Salud Mental", "https://www.unx.edu.ar/sm/")])

    def test_la_sigla_en_un_nombre_a_los_gritos(self):
        self.assertEqual(nombre_de_posgrado("DOCTORADO DE LA UNRN MENCIÓN EN ARQUITECTURA")[0],
                         "Doctorado de la UNRN Mención en Arquitectura")

    def test_el_titulo_de_especialista(self):
        self.assertEqual(nombre_de_posgrado("Especialista En Comunicación Corporativa E Institucional")[0],
                         "Especialización en Comunicación Corporativa E Institucional")
        self.assertIsNone(nombre_de_posgrado("Especialización Superior en Neurodiversidad"))

    def test_el_estado_de_la_inscripcion(self):
        for texto in ("Especialización en Asesoramiento Jurídico de Empresa (preinscripción online 2027)",
                      "Especialización en Asesoramiento Jurídico de Empresa (inscripción abierta 2026)",
                      "Especialización en Asesoramiento Jurídico de Empresa (en curso 2025-2026)",
                      "Especialización en Asesoramiento Jurídico de Empresa – Sede San Rafael"):
            self.assertEqual(nombre_de_posgrado(texto)[0], "Especialización en Asesoramiento Jurídico de Empresa")

    def test_el_titulo_bajo_el_nombre(self):
        html = ("<ul><li><h3>Maestría en Biotecnología Agropecuaria</h3><p>Magíster en Biotecnología "
                "Agropecuaria con Orientación Vegetal</p></li><li><p>Magíster en Diabetes</p></li></ul>")
        self.assertEqual(sorted(p.nombre for p in leer_lista(html, PAGINA, ("unx.edu.ar",))),
                         ["Maestría en Biotecnología Agropecuaria", "Maestría en Diabetes"])

    def test_una_descripcion_que_nombra_la_carrera(self):
        self.assertIsNone(nombre_de_posgrado("La Maestría en Estudios Feministas busca transversalizar"))

    def test_una_nota_al_pie(self):
        self.assertEqual(nombre_de_posgrado("Maestría en Cereales * * Dictada en conjunto con Ingeniería")[0],
                         "Maestría en Cereales")

    def test_el_tema_entre_comillas(self):
        self.assertEqual(nombre_de_posgrado("Maestría “Docencia Universitaria“")[0],
                         "Maestría en Docencia Universitaria")

    def test_resolucion_de_conflictos_es_un_tema(self):
        self.assertIsNotNone(nombre_de_posgrado("Especialización en Medios Alternativos de Resolución de Conflictos"))

    def test_una_tarjeta_que_es_solo_una_imagen(self):
        html = '<div class="b"><a href="/p/n1" title="Doctorado en Gestión"><img src="x.jpg"></a></div>'
        self.assertEqual([p.nombre for p in leer_lista(html, PAGINA, ("unx.edu.ar",), ".b")],
                         ["Doctorado en Gestión"])


class ElEnlaceDeLaTarjeta(unittest.TestCase):
    def test_la_tarjeta_de_un_solo_programa(self):
        html = ('<div class="card"><a href="/p/enf"><img src="x.jpg"></a>'
                '<h2>Especialización en Enfermería</h2><a href="/p/enf">Más información</a></div>')
        self.assertEqual([p.url for p in leer_lista(html, PAGINA, ("unx.edu.ar",))],
                         ["https://www.unx.edu.ar/p/enf"])

    def test_la_seccion_de_una_facultad_no_es_la_pagina_de_sus_programas(self):
        html = ('<div><h3><a href="https://derecho.unx.edu.ar/web/">Facultad de Derecho</a></h3>'
                '<ul><li>Doctorado en Derecho</li><li>Maestría en Criminología</li></ul></div>')
        self.assertEqual({p.url for p in leer_lista(html, PAGINA, ("unx.edu.ar",))}, {PAGINA})


if __name__ == "__main__":
    unittest.main()
