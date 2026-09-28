import unittest

from rumbo_scraper.database.completar_undef import bloques


class CompletarUndef(unittest.TestCase):
    def test_un_bloque_por_carrera(self):
        html = """<details><summary>Licenciatura en Administración Naval (Formación militar)</summary>
        <div><p>Título que otorga</p><p>: Licenciado en Administración Naval</p><p>Duración</p><p>: 5 años.</p></div></details>"""
        self.assertEqual(bloques(html)["licenciatura en administracion naval"],
                         {"nombre": "Licenciatura en Administración Naval (Formación militar)",
                          "titulo": "Licenciado en Administración Naval", "duracion": 5.0})


if __name__ == "__main__":
    unittest.main()
