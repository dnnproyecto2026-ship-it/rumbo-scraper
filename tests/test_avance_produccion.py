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
