import unittest

from rumbo_scraper.database.load_convenios import _es_propia, _original, _para_leer, _url_de, verificar_relevados
from rumbo_scraper.parsers.convenios import nombrada_en


class NombradaEn(unittest.TestCase):
    def test_por_sus_palabras_sin_tildes_ni_idioma(self):
        self.assertTrue(nombrada_en("Universidad de Brasilia", "convenio con la Universidade de Brasília"))
        self.assertTrue(nombrada_en("Università degli Studi di Padova", "Universita Degli Studi di Padova"))

    def test_por_su_sigla(self):
        self.assertTrue(nombrada_en("Universidad Autónoma de San Luis Potosí (UASLP)", "Firmamos con la UASLP"))

    def test_otra_universidad_no(self):
        self.assertFalse(nombrada_en("Universidad de Salamanca", "Universidad de Sevilla y Universidad de Málaga"))
        self.assertFalse(nombrada_en("Universidad de Granma", "Universidad de Camagüey"))

    def test_nombre_largo_puede_perder_una_palabra(self):
        self.assertTrue(nombrada_en("Universidad Francisco de Paula Santander Ocaña",
                                    "Universidad Francisco de Paula Santander"))
        self.assertFalse(nombrada_en("Universidad de Paula Santander", "Universidad de Paula"))


class Direcciones(unittest.TestCase):
    def test_la_url_de_una_fuente_comentada(self):
        self.assertEqual(_url_de("https://x.edu.ar/a.pdf (memoria 2019, p. 4)"), "https://x.edu.ar/a.pdf")

    def test_documentos_de_google(self):
        self.assertEqual(_para_leer("https://docs.google.com/spreadsheets/d/abcDEF_123/edit#gid=0"),
                         "https://docs.google.com/spreadsheets/d/abcDEF_123/htmlview")

    def test_copia_archivada(self):
        self.assertEqual(_original("https://web.archive.org/web/2020/https://uno.edu.ar/x"),
                         "https://uno.edu.ar/x")


class _LectorFijo:
    def __init__(self, paginas):
        self.paginas = paginas
        self.crudos = paginas

    def texto(self, url):
        return self.paginas.get(url, "")

    def documentos(self, url):
        return [u for u in self.paginas if u.startswith(url + "/") and u.endswith(".pdf")]


class Verificar(unittest.TestCase):
    def test_acepta_lo_que_su_pagina_nombra_y_rechaza_lo_demas(self):
        lector = _LectorFijo({
            "https://www.uno.edu.ar/n/1": "Convenio con la Universidad Nacional Mayor de San Marcos",
            "https://socia.edu.pe/c": "Convenios vigentes: Universidad de Lima",
        })
        relevados = {"Universidad Nacional del Oeste": {"slug": "uno", "sitio_web": "https://www.uno.edu.ar",
                     "convenios": [
                         {"universidad": "Universidad Nacional Mayor de San Marcos", "pais": "Perú",
                          "fuente": "https://www.uno.edu.ar/n/1"},
                         {"universidad": "Universidad de Salamanca", "pais": "España",
                          "fuente": "https://www.uno.edu.ar/n/1"},
                         {"universidad": "Universidad de Lima", "pais": "Perú",
                          "fuente": "https://socia.edu.pe/c (sitio de la socia)"}]}}
        aceptados, rechazados = verificar_relevados(relevados, lector)
        self.assertEqual([f["universidad_destino"] for f in aceptados["Universidad Nacional del Oeste"]],
                         ["Universidad Nacional Mayor de San Marcos"])
        self.assertEqual([r["motivo"] for r in rechazados],
                         ["la página no la nombra", "no es su sitio y no la nombra a ella"])

    def test_la_lista_que_la_pagina_enlaza_cuenta_como_ella(self):
        lector = _LectorFijo({"https://www.uno.edu.ar/convenios": "Convenios internacionales: ver la lista",
                              "https://www.uno.edu.ar/convenios/lista.pdf": "Universidad de Salamanca (España)"})
        relevados = {"Universidad Nacional del Oeste": {"slug": "uno", "sitio_web": "https://www.uno.edu.ar",
                     "convenios": [{"universidad": "Universidad de Salamanca", "pais": "España",
                                    "fuente": "https://www.uno.edu.ar/convenios"}]}}
        aceptados, rechazados = verificar_relevados(relevados, lector)
        self.assertEqual(len(aceptados["Universidad Nacional del Oeste"]), 1)
        self.assertEqual(rechazados, [])

    def test_una_planilla_que_su_sitio_enlaza_es_propia(self):
        lector = _LectorFijo({"https://filo.uba.ar/convenios": '<a href="https://docs.google.com/spreadsheets/d/1omQWuSIx2p2HVZ5uvdG/edit">'})
        fuente = "https://docs.google.com/spreadsheets/d/1omQWuSIx2p2HVZ5uvdG/edit (enlazada desde https://filo.uba.ar/convenios)"
        self.assertTrue(_es_propia(_url_de(fuente), fuente, "https://www.uba.ar", lector))


if __name__ == "__main__":
    unittest.main()
