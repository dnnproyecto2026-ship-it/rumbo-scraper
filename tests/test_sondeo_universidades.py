import unittest

from rumbo_scraper.database.sondeo_universidades import clasificar


class Clasificar(unittest.TestCase):
    def test_el_plan_en_la_pagina(self):
        texto = " ".join(f"Primer año Álgebra Segundo año Cálculo Tercer año Física {'materia ' * 80}" for _ in range(3))
        self.assertEqual(clasificar("https://u.edu.ar/c/", f"<html><body><p>{texto}</p></body></html>", 200),
                         ("plan_en_pagina", ""))

    def test_un_pdf_que_se_llama_plan(self):
        html = '<a href="/doc/plan-de-estudios-abogacia.pdf">Descargar</a>'
        self.assertEqual(clasificar("https://u.edu.ar/c/", html, 200),
                         ("pdf_del_plan", "https://u.edu.ar/doc/plan-de-estudios-abogacia.pdf"))

    def test_otra_pagina_del_mismo_sitio_y_no_de_otro(self):
        html = '<a href="https://otro.com/plan-de-estudios">Plan de estudios</a><a href="/plan">Plan de estudios</a>'
        self.assertEqual(clasificar("https://www.u.edu.ar/c/", html, 200), ("plan_en_otra_pagina", "https://www.u.edu.ar/plan"))

    def test_bloqueo_y_pagina_sin_plan(self):
        self.assertEqual(clasificar("https://u.edu.ar/c/", "<html>Just a moment...</html>", 403)[0], "caida")
        self.assertEqual(clasificar("https://u.edu.ar/c/", "<p>Requisitos de ingreso</p>" * 200, 200)[0], "sin_plan_publicado")

    def test_cloudflare_en_los_scripts_no_es_un_bloqueo(self):
        html = '<script src="https://cdnjs.cloudflare.com/x.js"></script><p>' + "Requisitos de ingreso " * 200 + "</p>"
        self.assertEqual(clasificar("https://u.edu.ar/c/", html, 200)[0], "sin_plan_publicado")


class TextoDelPdf(unittest.TestCase):
    def test_un_pdf_sin_texto_no_cuenta_caracteres(self):
        import shutil
        import subprocess
        import tempfile
        from pathlib import Path

        from rumbo_scraper.database.sondeo_universidades import texto_del_pdf

        if not shutil.which("pdftotext"):
            self.skipTest("pdftotext no está")
        with tempfile.TemporaryDirectory() as carpeta:
            vacio = Path(carpeta) / "v.pdf"
            vacio.write_bytes(b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
                              b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 100 100]>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF")
            self.assertLess(texto_del_pdf(vacio.read_bytes()), 300)


class PonerAlDia(unittest.TestCase):
    def test_quita_las_paginas_que_ya_tienen_plan_y_actualiza_la_cuenta(self):
        from rumbo_scraper.database.sondeo_universidades import poner_al_dia

        filas = [["UCH", "https://a", "pdf_con_texto", "x.pdf", "3"], ["UCH", "https://b", "js", "", "2"],
                 ["UNR", "https://c", "caida", "", "1"]]
        vigentes, quitadas = poner_al_dia(filas, [("UCH", "https://a", 1), ("UNR", "https://c", 1)])
        self.assertEqual(vigentes, [["UCH", "https://a", "pdf_con_texto", "x.pdf", "1"],
                                    ["UNR", "https://c", "caida", "", "1"]])
        self.assertEqual(quitadas, 1)
