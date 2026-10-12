import unittest

from rumbo_scraper.parsers import fotos


class Fotos(unittest.TestCase):
    def test_kept_by_its_own_words(self):
        html = """<main><figure><img src="/f/edificio-central-1024x683.jpg" alt="Edificio central">
        <figcaption>Fachada del edificio central. Foto: Prensa UX</figcaption></figure>
        <img src="/f/logo.png" alt="Logo"><img src="/f/IMG_2031.jpg" alt=""></main>"""
        [c] = fotos.imagenes_de(html, "https://www.ux.edu.ar/institucional")
        self.assertEqual(c.url_imagen, "https://www.ux.edu.ar/f/edificio-central.jpg")
        self.assertEqual(c.tipo, "campus")
        self.assertEqual(c.credito, "Prensa UX")
        self.assertEqual(fotos.descripcion(c), "Fachada del edificio central")

    def test_portraits_and_events_are_not_spaces(self):
        self.assertIsNone(fotos.tipo_de("El rector en el aula magna"))
        self.assertIsNone(fotos.tipo_de("Jornada de laboratorios abiertos"))
        self.assertEqual(fotos.tipo_de("Laboratorio de química"), "laboratorio")

    def test_page_about_one_space_names_its_photographs(self):
        html = '<h1>Biblioteca Central</h1><img src="/f/DSC_0045.jpg">'
        [c] = fotos.imagenes_de(html, "https://www.ux.edu.ar/biblioteca")
        self.assertEqual((c.tipo, c.por_la_pagina), ("biblioteca", "Biblioteca Central"))
        self.assertEqual(fotos.imagenes_de(html.replace("Biblioteca Central", "Novedades"),
                                           "https://www.ux.edu.ar/biblioteca"), [])

    def test_resized_copies_lead_to_the_original(self):
        self.assertEqual(fotos.original_de("https://x.edu.ar/sites/default/files/styles/large/public/a/b.jpg?itok=1"),
                         "https://x.edu.ar/sites/default/files/a/b.jpg")
        self.assertEqual(fotos.desenvolver("https://x.edu.ar/_next/image?url=%2Ff%2Fa.jpg&w=3840"),
                         "https://x.edu.ar/f/a.jpg")


if __name__ == "__main__":
    unittest.main()
