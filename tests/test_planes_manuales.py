import unittest

from rumbo_scraper import verificacion as v
from rumbo_scraper.database.planes_manuales import materias_de, revisar


class _Fuentes:
    def __init__(self, texto):
        self.texto = texto

    def leer(self, url):
        return {"ok": True, "texto": v.plano(self.texto)}


class MateriasDe(unittest.TestCase):
    def test_year_and_name(self):
        self.assertEqual(materias_de("1 | Introducción al Derecho\n\n2 | Derecho Civil I"),
                         [("Introducción al Derecho", 1), ("Derecho Civil I", 2)])

    def test_name_alone(self):
        self.assertEqual(materias_de("Matemática\nFísica"), [("Matemática", None), ("Física", None)])

    def test_mixed_or_unreadable_lines_are_sent_back(self):
        self.assertIsInstance(materias_de("1 | Matemática\nFísica"), str)
        self.assertIsInstance(materias_de("1 | Matemática | anual"), str)



class Revisar(unittest.TestCase):
    UNIVERSIDAD = {"id": "u", "nombre_corto": "USAL", "sitio_web": "https://www.usal.edu.ar"}
    MATERIAS = [f"Materia Numero {n}" for n in range(1, 14)]
    FILA = {"link_del_plan_usado": "https://www.usal.edu.ar/plan.png", "cargado_por": "IA (Claude)",
            "revisado_por": "", "materias (una por renglón: año | nombre)":
            "\n".join(f"{1 + i // 7} | {m}" for i, m in enumerate(MATERIAS))}

    def carrera(self, nombre):
        return {"id": "c", "universidad_id": "u", "nombre_carrera": nombre, "duracion_anios": 4}

    def test_a_completion_cycle_own_two_year_plan_is_whole(self):
        motivo, materias, _ = revisar(self.FILA, self.carrera(
            "Licenciatura en Criminología – Ciclo de Complementación Curricular"), self.UNIVERSIDAD, set(),
            _Fuentes("\n".join(self.MATERIAS)))
        self.assertEqual((motivo, len(materias)), ("", 13))

    def test_a_degree_stopping_in_its_second_year_is_not(self):
        motivo, _, _ = revisar(self.FILA, self.carrera("Licenciatura en Criminología"), self.UNIVERSIDAD, set(),
                               _Fuentes("\n".join(self.MATERIAS)))
        self.assertIn("completo", motivo)

    def test_a_name_not_in_the_document_sends_the_ai_row_back(self):
        motivo, _, _ = revisar(self.FILA, self.carrera("Licenciatura en Criminología – Ciclo de Complementación "
                               "Curricular"), self.UNIVERSIDAD, set(), _Fuentes("\n".join(self.MATERIAS[:-1])))
        self.assertIn("Materia Numero 13", motivo)


    def test_a_document_that_says_it_is_a_completion_cycle_is_judged_as_one(self):
        fila = {**self.FILA, "link_del_plan_usado": "https://www.usal.edu.ar/plan.pdf"}
        fuentes = _Fuentes("LICENCIATURA EN HOTELERÍA Y TURISMO (Ciclo de Complementación Curricular) "
                           + " ".join(self.MATERIAS))
        motivo, materias, _ = revisar(fila, self.carrera("Licenciatura en Hotelería y Turismo"),
                                      self.UNIVERSIDAD, set(), fuentes)
        self.assertEqual((motivo, len(materias)), ("", 13))


if __name__ == "__main__":
    unittest.main()
