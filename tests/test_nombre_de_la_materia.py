"""Tests for what a plan line exports as a subject."""

import unittest

from rumbo_scraper.database.exportar_catalogo import nombre_de_la_materia


class LoQueNoEsUnaMateria(unittest.TestCase):
    def test_no_sale(self):
        for linea in (
            "¿Cuánto dura la carrera?",
            "Inscribite a tus materias. ¡Listo! Ya empezaste tu camino en la Kennedy.",
            "TÉCNICO/A UNIVERSITARIO/A EN ADMINISTRACIÓN DE EMPRESAS",
            "Licenciado/a en Ciencias del Comportamiento",
            "Licenciatura en Turismo",
            "Tecnicatura Universitaria en Enfermería en Siglo 21",
            "INGENIERO EN INFORMÁTICA",
            "ABOGADO",
            "CONTADOR PÚBLICO",
            "Quiero inscribirme",
            "Consultas",
            "Consultas e inscripción enviar un correo a",
            "Programas relacionados",
            "Universidad Kennedy",
            "Carrera de Grado",
            "Primer semestre Segundo semestre",
            "Segundo Cuatrimestre Finanzas Empresariales Management del Capital Humano",
            "TITULO LICENCIADO A EN GESTIÓN DE EMPRESAS TURÍSTICAS CARGA HORARIA TOTAL",
        ):
            with self.subTest(linea=linea):
                self.assertIsNone(nombre_de_la_materia(linea))


class UnaMateria(unittest.TestCase):
    def test_sale_tal_cual(self):
        for linea in (
            "Materiales Metálicos",
            "Ingeniería de Software I",
            "Economía del Comportamiento",
            "Universidad y Sociedad",
            "Derecho Constitucional",
            "Consultoría Organizacional",
            "Derechos Humanos ¿paradigma vigente en el mundo globalizado?",
        ):
            with self.subTest(linea=linea):
                self.assertEqual(nombre_de_la_materia(linea), linea)

    def test_la_que_viene_en_mayusculas_sale_en_minusculas(self):
        for linea, materia in (
            ("TÍTULOS VALORES Y CONCURSOS", "Títulos valores y concursos"),
            ("PSICOLOGÍA EN LAS EMPRESAS", "Psicología en las empresas"),
            ("MATEMÁTICA II", "Matemática II"),
            ("ANÁLISIS MATEMÁTICO IV", "Análisis matemático IV"),
            ("ARTE", "ARTE"),
        ):
            with self.subTest(linea=linea):
                self.assertEqual(nombre_de_la_materia(linea), materia)

    def test_palermo_sin_los_codigos_ni_el_modulo(self):
        for linea, materia in (
            ("Diseño Industrial I 022096 | 026490 ESTILO Personalizar para diferenciar (Autor.)",
             "Diseño Industrial I"),
            ("Producción Gráfica 020494 | 026643 | 26183 GESTIÓN Concretar mis proyectos",
             "Producción Gráfica"),
            ("Comercialización II 021203 - 025962 EMPRENDER Plan de Negocios",
             "Comercialización II"),
        ):
            with self.subTest(linea=linea):
                self.assertEqual(nombre_de_la_materia(linea), materia)


if __name__ == "__main__":
    unittest.main()

    def test_lo_que_rodea_al_plan_en_el_documento_no_sale(self):
        for linea in (
            "clorenzano@untref.edu.ar",
            "de Carga",
            "sector",
            "Rios Cañavate JL. Fitoterapia Reproexpres ediciones",
            "norma.htm Ley",
            "Manual de Medicina Legal. Buenos Aires Ed Akadia Ed. Trillas",
            "https reis.cis.es REIS PDF",
            "UNAJ c c c c c c c c c c",
            "* a partir del plan de estudios 2017, todos los alumnos ingresantes",
            "(***) La carga horaria total mínima que el alumno deberá acreditar",
            "Electiva VI LIBERTAD DE ELEGIR Opciones de orientación profesional y creativa "
            "Electiva VI LIBERTAD DE ELEGIR Opciones de orientación profesional y creativa extra",
        ):
            self.assertIsNone(nombre_de_la_materia(linea), linea)

    def test_la_vineta_y_el_punto_final_no_son_del_nombre(self):
        self.assertEqual(nombre_de_la_materia("-Cambio climático."), "Cambio climático")
        self.assertEqual(nombre_de_la_materia("• Derecho Ambiental"), "Derecho Ambiental")
        self.assertEqual(nombre_de_la_materia("Seminario I: Temas de Actualidad"),
                         "Seminario I: Temas de Actualidad")
        self.assertEqual(nombre_de_la_materia("(**) Análisis Político"), "Análisis Político")
        self.assertEqual(nombre_de_la_materia("Desarrollo de proyectos culturales, audiovisuales y "
                                              "editoriales"),
                         "Desarrollo de proyectos culturales, audiovisuales y editoriales")
