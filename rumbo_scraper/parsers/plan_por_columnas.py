"""The subjects of a plan published as a table whose header names its columns.

Most national universities publish a career's plan as the annex of the
resolution that approved it, and the annex is a table with a header row:

    Año | Cuat. | Código | Asignatura-Actividad | Área | Correlatividades   (UNM)
    Cuat | Asignaturas | Cód. | CG | Hs. | Correlativas                    (UNMdP)

The header says which column is the subject and which the year or the term,
and that is all this relies on: no position is assumed. The rest of each PDF
-- the "VISTO el Expediente", the profile of the graduate, the timetable --
is prose or other tables, and is never read.

What is taken:

- rows under a header that names a subject column, and the tables after it
  that have the same number of columns (a table the page break cut);
- the year from a year column; failing that, from a term column when the
  terms run past two ("7" is the seventh term, the fourth year); failing
  that, from a heading row in the subject column ("PRIMER AÑO");
- when the header has a year or term column, a row that leaves it empty is
  not part of the sequence -- the optional seminars at the end -- and is
  left out.

A plan is only returned when it looks like one: at least ten subjects, and a
year for nearly all of them when the table has a year column. Anything less
is returned empty, never half-read.
"""

from __future__ import annotations

import re
from typing import Iterable

_TILDES = str.maketrans("áéíóúÁÉÍÓÚñÑ", "aeiouAEIOUnN")

# The whole cell is the column's name: a subject can start with "Materia".
_MATERIA = re.compile(r"(asignaturas?|materias?|asignatura-actividad|espacios? curricular(es)?|"
                      r"unidad(es)? curricular(es)?|actividad(es)? curricular(es)?|"
                      r"nombre de la (asignatura|materia)|asignaturas? obligatorias?)")
_ANIO = re.compile(r"^(ano|anio|ano de cursada|nivel)$")
_CUATRIMESTRE = re.compile(r"^(cuat\.?|cuatr\.?|cuatrimestre|semestre|periodo)$")
_ORDINAL = {"primer": 1, "primero": 1, "segundo": 2, "tercer": 3, "tercero": 3, "cuarto": 4,
            "quinto": 5, "sexto": 6, "septimo": 7}
_ANIO_EN_FILA = re.compile(r"^(" + "|".join(_ORDINAL) + r")\s+ano$|^(\d)\s*[°º]?\s*ano$")
_NO_ES_MATERIA = re.compile(r"^(total|subtotal|carga horaria|horas|creditos|optativ|electiv|"
                            r"seminarios? optativ|ciclo|nucleo|bloque|area)\b")

MINIMO = 10
PARTE_CON_ANIO = 0.8


def _plano(texto: str | None) -> str:
    return " ".join((texto or "").translate(_TILDES).lower().split())


def _numero(texto: str) -> int | None:
    match = re.match(r"^(\d{1,2})\b", texto.strip())
    return int(match.group(1)) if match else None


def _encabezado(fila: list[str]) -> tuple[int, int | None, int | None] | None:
    """(subject, year, term) column indexes, if the row is a plan's header."""
    materia = anio = termino = None
    for i, celda in enumerate(fila):
        plano = _plano(celda)
        if materia is None and _MATERIA.fullmatch(plano):
            materia = i
        elif anio is None and _ANIO.match(plano):
            anio = i
        elif termino is None and _CUATRIMESTRE.match(plano):
            termino = i
    return (materia, anio, termino) if materia is not None else None


def leer_tablas(tablas: Iterable[list[list[str | None]]]) -> list[tuple[str, int | None]]:
    """(subject, year) for the plan's subjects, or nothing."""
    filas: list[tuple[str, int | None, int | None]] = []  # name, year, term
    columnas: tuple[int, int | None, int | None] | None = None
    ancho = 0
    anio_de_fila: int | None = None

    for tabla in tablas:
        tabla = [[" ".join((c or "").split()) for c in fila] for fila in tabla]
        encabezados = [(i, _encabezado(f)) for i, f in enumerate(tabla)]
        encabezado = next(((i, e) for i, e in encabezados if e), None)
        if columnas is None:
            if not encabezado:
                continue
            inicio, columnas = encabezado[0] + 1, encabezado[1]
            ancho = len(tabla[encabezado[0]])
        elif encabezado or len(tabla[0]) != ancho:
            # A second header, or a table of another shape: the plan's table
            # is over (what follows is electives, equivalences, another plan).
            break
        else:
            inicio = 0

        materia, anio, termino = columnas
        for fila in tabla[inicio:]:
            if len(fila) <= materia:
                continue
            nombre = fila[materia]
            plano = _plano(nombre)
            if not plano:
                continue
            en_fila = _ANIO_EN_FILA.match(plano)
            if en_fila:
                numero = en_fila.group(1) or en_fila.group(2)
                anio_de_fila = int(numero) if numero.isdigit() else _ORDINAL[numero]
                continue
            if _NO_ES_MATERIA.match(plano) or not re.search(r"[a-z]{3}", plano):
                continue
            valor_anio = _numero(fila[anio]) if anio is not None and anio < len(fila) else None
            valor_termino = (_numero(fila[termino])
                             if termino is not None and termino < len(fila) else None)
            if anio is not None and valor_anio is None and anio_de_fila is None:
                continue  # an optional seminar, outside the sequence
            filas.append((nombre, valor_anio or anio_de_fila, valor_termino))

    # A term column that runs past two counts terms from the start.
    terminos = [t for _, _, t in filas if t]
    acumulado = bool(terminos) and max(terminos) > 2
    materias: list[tuple[str, int | None]] = []
    vistas: set[str] = set()
    for nombre, anio, termino in filas:
        if anio is None and termino and acumulado:
            anio = (termino + 1) // 2
        if _plano(nombre) in vistas:
            continue
        vistas.add(_plano(nombre))
        materias.append((nombre, anio if anio and 1 <= anio <= 7 else None))

    if len(materias) < MINIMO:
        return []
    con_anio = sum(1 for _, a in materias if a)
    if columnas and (columnas[1] is not None or columnas[2] is not None or con_anio):
        if con_anio < PARTE_CON_ANIO * len(materias):
            return []
    return materias


def leer_pdf(ruta: str) -> list[tuple[str, int | None]]:
    import pdfplumber

    with pdfplumber.open(ruta) as pdf:
        tablas = [tabla for pagina in pdf.pages for tabla in pagina.extract_tables()]
    return leer_tablas(tablas)
