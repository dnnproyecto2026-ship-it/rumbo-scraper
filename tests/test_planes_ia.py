import unittest

from rumbo_scraper.database.planes_ia import a_renglones, enlace_candidato, respuesta_a_materias


class PlanesIa(unittest.TestCase):
    def test_lee_el_json_aunque_venga_con_texto_alrededor(self):
        salida = 'Acá va:\n{"completo": true, "materias": [{"anio": 1, "nombre": "Álgebra"}, {"anio": 2, "nombre": " Física  II "}], "motivo": ""}'
        self.assertEqual(respuesta_a_materias(salida), ([("Álgebra", 1), ("Física II", 2)], ""))

    def test_un_plan_no_completo_no_da_materias(self):
        materias, motivo = respuesta_a_materias('{"completo": false, "materias": [], "motivo": "es otra carrera"}')
        self.assertEqual((materias, motivo), ([], "es otra carrera"))

    def test_sin_json_o_con_anios_mezclados_no_se_toma(self):
        self.assertEqual(respuesta_a_materias("no sé")[0], [])
        mezcla = '{"completo": true, "materias": [{"anio": 1, "nombre": "A"}, {"anio": null, "nombre": "B"}]}'
        self.assertEqual(respuesta_a_materias(mezcla)[0], [])

    def test_el_enlace_armado_por_un_script_no_sirve(self):
        self.assertIsNone(enlace_candidato("plan_en_otra_pagina", "https://a", "https://a/' + result_alt[e].archivo + '.pdf"))
        self.assertEqual(enlace_candidato("pdf_con_texto", "https://a", "https://a/plan.pdf"), "https://a/plan.pdf")
        self.assertEqual(enlace_candidato("plan_en_pagina", "https://a/carrera", ""), "https://a/carrera")
        self.assertIsNone(enlace_candidato("js", "https://a", ""))

    def test_renglones_con_y_sin_anio(self):
        self.assertEqual(a_renglones([("A", 1), ("B", 2)]), "1 | A\n2 | B")
        self.assertEqual(a_renglones([("A", None)]), "A")
