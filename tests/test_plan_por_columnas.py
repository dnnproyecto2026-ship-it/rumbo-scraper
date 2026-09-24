"""Tests for the plan read off a table whose header names its columns."""

import unittest

from rumbo_scraper.parsers.plan_por_columnas import leer_tablas


def materias(n, anio_de=lambda i: str(i // 4 + 1)):
    return [[anio_de(i), "1", str(1500 + i), f"Materia Número {i}", "Área"] for i in range(n)]


ENCABEZADO_UNM = ["Año", "Cuat.", "Código", "Asignatura-Actividad", "Área Epistémica"]


class LeerPorColumnas(unittest.TestCase):
    def test_el_anio_sale_de_su_columna(self):
        plan = leer_tablas([[ENCABEZADO_UNM] + materias(12)])
        self.assertEqual(len(plan), 12)
        self.assertEqual(plan[0], ("Materia Número 0", 1))
        self.assertEqual(plan[11], ("Materia Número 11", 3))

    def test_la_tabla_que_sigue_con_la_misma_forma_es_la_misma(self):
        plan = leer_tablas([[ENCABEZADO_UNM] + materias(6), materias(12)[6:]])
        self.assertEqual(len(plan), 12)

    def test_un_segundo_encabezado_cierra_el_plan(self):
        optativas = [["Seminarios-Taller Optativos", "", "", "", ""], ENCABEZADO_UNM,
                     ["", "", "1563A", "Derecho de las Niñeces", "Derecho Privado"]]
        plan = leer_tablas([[ENCABEZADO_UNM] + materias(12), optativas])
        self.assertNotIn("Derecho de las Niñeces", [m for m, _ in plan])

    def test_sin_anio_en_su_fila_no_es_de_la_secuencia(self):
        filas = materias(12) + [["", "", "1563A", "Seminario Optativo de Género", "Área"]]
        plan = leer_tablas([[ENCABEZADO_UNM] + filas])
        self.assertNotIn("Seminario Optativo de Género", [m for m, _ in plan])

    def test_el_cuatrimestre_acumulado_da_el_anio(self):
        filas = [["Cuat", "Asignaturas", "Cód."]] + [
            [str(i // 2 + 1), f"Asignatura Número {i}", "633"] for i in range(12)]
        plan = leer_tablas([filas])
        self.assertEqual(plan[-1], ("Asignatura Número 11", 3))  # sexto cuatrimestre

    def test_el_anio_escrito_como_fila(self):
        filas = [["Cuat", "Asignaturas", "Cód."], ["", "PRIMER AÑO", ""]] + [
            ["", f"Asignatura Número {i}", "633"] for i in range(6)] + [
            ["", "SEGUNDO AÑO", ""]] + [["", f"Otra Asignatura {i}", "634"] for i in range(6)]
        plan = leer_tablas([filas])
        self.assertEqual((plan[0][1], plan[-1][1]), (1, 2))

    def test_menos_de_diez_materias_no_es_un_plan(self):
        self.assertEqual(leer_tablas([[ENCABEZADO_UNM] + materias(6)]), [])

    def test_sin_encabezado_no_se_lee_nada(self):
        self.assertEqual(leer_tablas([materias(20)]), [])


    def test_el_cuatrimestre_como_fila_entre_las_materias(self):
        filas = [["Núcleo", "Asignatura", "Créditos"]]
        for termino, nombre in ((2, "Segundo"), (5, "Quinto"), (7, "Séptimo")):
            filas.append([f"{nombre} Cuatrimestre"])
            filas += [["Básico", f"Materia {termino}-{i} de Programación", "16"] for i in range(4)]
        plan = leer_tablas([filas])
        self.assertEqual((plan[0][1], plan[4][1], plan[-1][1]), (1, 3, 4))


if __name__ == "__main__":
    unittest.main()
