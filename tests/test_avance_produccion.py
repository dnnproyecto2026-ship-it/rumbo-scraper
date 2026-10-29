import unittest

from rumbo_scraper.database.avance_produccion import diferencia


def foto(planes, con_plan_ba):
    return {"totales": {"instituciones": 10, "ofertas_publicadas": 100, "carreras": 50, "planes": planes, "materias": 900},
            "por_tipo": [], "por_provincia": [{"clave": "Buenos Aires", "ofertas": 40, "con_plan": con_plan_ba}]}


class Diferencia(unittest.TestCase):
    def test_sin_foto_anterior_no_compara(self):
        self.assertEqual(diferencia(foto(5, 10), None), ["(primera instantánea: sin comparación)"])

    def test_dice_lo_que_se_movio(self):
        lineas = diferencia(foto(8, 14), foto(5, 10))
        self.assertIn("planes: 5 -> 8 (+3)", lineas)
        self.assertIn("provincia Buenos Aires: con plan 10 -> 14 (+4), ofertas 40 -> 40", lineas)
        self.assertNotIn("carreras: 50 -> 50 (+1)", lineas)

    def test_los_posgrados_se_comparan_aparte(self):
        vieja = foto(5, 10)
        nueva = foto(5, 10)
        vieja["posgrados"] = [{"clave": "publica", "ofertas": 100, "con_plan": 5, "con_titulo": 80, "con_duracion": 20}]
        nueva["posgrados"] = [{"clave": "publica", "ofertas": 100, "con_plan": 5, "con_titulo": 85, "con_duracion": 40}]
        self.assertEqual(diferencia(nueva, vieja)[-1], "posgrados publica: título 80 -> 85, duración 20 -> 40")


class MotivosDeLasOfertasSinPlan(unittest.TestCase):
    def test_cada_oferta_sin_plan_lleva_el_motivo_de_su_pagina(self):
        from rumbo_scraper.database.avance_produccion import motivos_de

        pendientes = [("UCP", "https://ucp/a", 9), ("UCP", "https://ucp/b", 2), ("UNLP", "https://unlp/x", 4)]
        sondeo = {"https://ucp/a": "sin_plan_publicado", "https://ucp/b": "sin_plan_publicado", "https://unlp/x": "js"}
        self.assertEqual(motivos_de(pendientes, sondeo), {"sin_plan_publicado": 11, "js": 4})
        self.assertEqual(motivos_de([("U", "https://u/z", 3)], sondeo), {"sin_sondear": 3})
