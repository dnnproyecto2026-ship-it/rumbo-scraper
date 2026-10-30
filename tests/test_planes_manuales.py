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
        motivo, _, _ = revisar(self.FILA, self.carrera("Licenciatura en Geografía (Complementación)"),
                               self.UNIVERSIDAD, set(), _Fuentes("\n".join(self.MATERIAS)))
        self.assertEqual(motivo, "")

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


class TablaEnImagenDentroDelPdf(unittest.TestCase):
    def test_two_people_take_a_pdf_whose_table_is_a_picture(self):
        fila = {"link_del_plan_usado": "https://www.usal.edu.ar/plan.pdf", "cargado_por": "Claude (IA)",
                "revisado_por": "Una Persona", "notas": "tabla en imagen dentro del PDF",
                "materias (una por renglón: año | nombre)":
                "\n".join(f"{1 + i // 4} | Materia Numero {i}" for i in range(13))}
        carrera = {"id": "c", "universidad_id": "u", "nombre_carrera": "Licenciatura en Algo", "duracion_anios": 4}
        universidad = {"id": "u", "nombre_corto": "USAL", "sitio_web": "https://www.usal.edu.ar"}
        motivo, materias, imagen = revisar(fila, carrera, universidad, set(), _Fuentes("texto sin las materias"))
        self.assertEqual((motivo, len(materias), imagen), ("", 13, True))


class PlanCorto(unittest.TestCase):
    def test_twelve_names_without_years_or_five_for_a_one_year_title(self):
        from rumbo_scraper.database.planes_manuales import _plan_corto_entero
        doce = [(f"Materia Numero {n}", None) for n in range(12)]
        self.assertTrue(_plan_corto_entero(doce, 4))
        self.assertFalse(_plan_corto_entero(doce[:11], 4))
        self.assertTrue(_plan_corto_entero(doce[:5], 1))
        self.assertFalse(_plan_corto_entero(doce[:4], 1))
        self.assertTrue(_plan_corto_entero(doce[:3], 6, "Profesorado de Enseñanza Media y Superior en Psicología"))
        self.assertFalse(_plan_corto_entero(doce[:3], 6, "Licenciatura en Psicología"))

    def test_cut_names_and_gaps_in_the_years_are_not_whole(self):
        from rumbo_scraper.database.planes_manuales import _plan_corto_entero
        doce = [(f"Materia Numero {n}", None) for n in range(11)]
        self.assertFalse(_plan_corto_entero(doce + [("Historia de la", None)], 4))
        self.assertFalse(_plan_corto_entero([(f"Materia Numero {n}", 1 if n < 6 else 3) for n in range(12)], 4))


if __name__ == "__main__":
    unittest.main()
