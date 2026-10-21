import tempfile
import unittest
from pathlib import Path

from rumbo_scraper.mailing import armar_mensaje, elegir_destinatarios, enviados_hoy, leer_campana


class Mailing(unittest.TestCase):
    def test_solo_con_consentimiento_sin_bajas_ni_repetidos(self):
        filas = [
            {"email": "a@x.com", "nombre": "Ana", "consentimiento": "sí"},
            {"email": "A@x.com", "nombre": "Ana", "consentimiento": "si"},
            {"email": "b@x.com", "consentimiento": ""},
            {"email": "c@x.com", "consentimiento": "si"},
            {"email": "d@x.com", "consentimiento": "si"},
            {"email": "no-es-mail", "consentimiento": "si"},
        ]
        enviados = [{"campana": "becas", "email": "d@x.com", "fecha": "2026-10-20T10:00:00"}]
        elegidos, motivos = elegir_destinatarios(filas, "becas", {"c@x.com"}, enviados)
        self.assertEqual([c["email"] for c in elegidos], ["a@x.com"])
        self.assertEqual(motivos, {"sin_consentimiento": 1, "email_invalido": 1, "baja": 1, "ya_enviado": 1, "repetido": 1})

    def test_lo_enviado_en_otra_campana_no_cuenta(self):
        filas = [{"email": "d@x.com", "consentimiento": "1"}]
        enviados = [{"campana": "otra", "email": "d@x.com", "fecha": "2026-10-20T10:00:00"}]
        elegidos, _ = elegir_destinatarios(filas, "becas", set(), enviados)
        self.assertEqual(len(elegidos), 1)

    def test_cupo_diario_cuenta_solo_hoy(self):
        enviados = [{"fecha": "2026-10-21T09:00:00"}, {"fecha": "2026-10-20T23:59:00"}]
        self.assertEqual(enviados_hoy(enviados, "2026-10-21"), 1)

    def test_mensaje_con_pie_y_baja(self):
        with tempfile.TemporaryDirectory() as d:
            carpeta = Path(d) / "becas"
            carpeta.mkdir()
            (carpeta / "asunto.txt").write_text("Hola {nombre}\n", encoding="utf-8")
            (carpeta / "cuerpo.html").write_text("<p>Becas para {nombre}</p>", encoding="utf-8")
            campana = leer_campana(carpeta)
        msg = armar_mensaje(campana, {"email": "a@x.com", "nombre": "Ana"}, "Rumbo <hola@rumbo.ar>", "bajas@rumbo.ar")
        self.assertEqual(msg["Subject"], "Hola Ana")
        self.assertEqual(msg["List-Unsubscribe"], "<mailto:bajas@rumbo.ar?subject=BAJA>")
        texto = msg.get_body(("plain",)).get_content()
        self.assertIn("Becas para Ana", texto)
        self.assertIn("BAJA", texto)
        self.assertIn("bajas@rumbo.ar", msg.get_body(("html",)).get_content())


if __name__ == "__main__":
    unittest.main()
