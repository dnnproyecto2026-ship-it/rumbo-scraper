from rumbo_scraper.database.completar_unpa import anios, clave, plan_de


def test_anios():
    assert anios("5 Años") == 5
    assert anios("4 Años y 1 Ctre.") == 4.5
    assert anios("2 AÑOS Y 1 Ctre.") == 2.5
    assert anios("4.0") == 4
    assert anios("") is None


def test_clave():
    assert clave("Tec. Univ. en Rec. Nat. Renov. (Or. Prod. Frutihortícola)") == clave(
        "Tecnicatura Universitaria en Rec. Nat. Renov. (Or. Prod. Frutihortícola)")
    assert clave("Ingeniería Química - Título Intermedio Técnico Universitario en Análisis Químico") == clave(
        "Ingeniería Química")


PLAN = """\
Código                              Asignatura                               Cursado        Horas Semanales
                                                                    PRIMER AÑO
  1107      Introducción al Conocimiento Científico                             1ºC                   4
  0901      Análisis y Producción del Discurso                                    A                   2
                                                                   SEGUNDO AÑO
  1291      Optativa 1/Electiva 1                                               1ºC                   6
  1197      Didáctica de las Ciencias Económicas y                              2ºC                   6                             0929
            Empresariales
            Enfermería Materno Infantil y Cuidado de la
  2354                                                                         A                  8                              2350
            Mujer
  1625      Proyecto Final (**)                                                 1ºC                   10
                                      TÍTULO INTERMEDIO: TECNICO/A UNIVERSITARIO/A EN ANÁLISIS QUÍMICO
"""


def test_plan_de():
    assert plan_de(PLAN) == [
        ("Introducción al Conocimiento Científico", 1), ("Análisis y Producción del Discurso", 1),
        ("Didáctica de las Ciencias Económicas y Empresariales", 2),
        ("Enfermería Materno Infantil y Cuidado de la Mujer", 2), ("Proyecto Final", 2)]
