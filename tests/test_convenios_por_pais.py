import unittest

from rumbo_scraper.parsers import convenios as c


class LeerPorPais(unittest.TestCase):
    def test_one_university_per_line_under_its_country(self):
        lineas = ["Por otro lado, a través de ISEP permite intercambios en:", "Alemania", "FH Augsburg",
                  "Leibniz University Hannover", "Australia", "Deakin University",
                  "Si estás interesado escribinos."]
        filas = c.leer_por_pais(lineas, "f", "Universidad de Palermo")
        self.assertEqual([(f["universidad_destino"], f["pais"]) for f in filas],
                         [("FH Augsburg", "Alemania"), ("Leibniz University Hannover", "Alemania"),
                          ("Deakin University", "Australia")])

    def test_bullets_wrap_and_a_double_degree_is_left_out(self):
        lineas = ["ALEMANIA", "CONVENIOS DE INTERCAMBIO", "• Fachhochschule Aalen", "• University of Mannheim,",
                  "Business School", "CONVENIOS DE DOBLE TÍTULO", "• Fachhochschule Münster",
                  "Administración, Comercio", c._OTRA_COLUMNA, "CONVENIOS", "AUSTRALIA",
                  "CONVENIOS DE INTERCAMBIO", "• Flinders University of South", "Australia", "• Griffith University"]
        filas = c.leer_por_pais(lineas, "f", "Universidad de Belgrano")
        self.assertEqual([(f["universidad_destino"], f["pais"]) for f in filas],
                         [("Fachhochschule Aalen", "Alemania"), ("University of Mannheim, Business School", "Alemania"),
                          ("Flinders University of South Australia", "Australia"), ("Griffith University", "Australia")])


class LeerTablaPorPais(unittest.TestCase):
    def test_a_row_is_a_block_and_its_pieces_go_to_their_column(self):
        texto = "\n".join([
            "    DINAMARCA",
            "      Universidad            Ciudad        Demanda                   Áreas Sugeridas",
            "",
            "CBS - Copenhagen Business                                     Negocios, Administración, Comercio",
            "                            Copenhague",
            "         School                                                       Internacional, RR.II",
            "",
            "  Universidad de Sevilla    Sevilla                               Negocios",
            "",
            "   CONVENIOS EN AMÉRICA",
        ])
        filas = c.leer_tabla_por_pais(texto, "f", "Universidad Argentina de la Empresa")
        self.assertEqual([(f["universidad_destino"], f["pais"], f["ciudad"]) for f in filas],
                         [("CBS - Copenhagen Business School", "Dinamarca", "Copenhague"),
                          ("Universidad de Sevilla", "Dinamarca", "Sevilla")])


class LeerJsonLd(unittest.TestCase):
    def test_the_partners_a_page_declares(self):
        html = ('<script type="application/ld+json">{"@graph": [{"@type": "ItemList", "name": '
                '"Universidades con vinculación internacional", "itemListElement": [{"@type": "ListItem", '
                '"item": {"@type": "CollegeOrUniversity", "name": "Yale University"}}]}]}</script>')
        self.assertEqual([f["universidad_destino"] for f in c.leer_json_ld(html, "f")], ["Yale University"])
