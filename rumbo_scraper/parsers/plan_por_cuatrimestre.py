"""The subjects of a plan published as a table of four-month terms.

The Faculty of Engineering of the UBA publishes each career's plan as the
resolution that approved it, and every one lays the career out the same way:
the Ciclo Básico Común ("Primer y segundo cuatrimestre") with a code before
each subject, then one heading per term -- "TERCER CUATRIMESTRE" to "DÉCIMO
CUATRIMESTRE" -- over rows of subject, credits, hours and prerequisites. The
table ends at "TOTAL CRÉDITOS DEL PLAN"; what follows (the electives, the
equivalences with the old plan) is not the plan's compulsory subjects.

The tables are read as tables (pdfplumber), not as laid-out text: a name too
long for its cell wraps, and only the cell keeps its pieces together.

The year is the document's: the CBC is the first and second term, so the
first year, and term n is year ceil(n / 2).
"""

from __future__ import annotations

import re
from typing import Iterable

_ORDINAL = {
    "primer": 1, "primero": 1, "segundo": 2, "tercer": 3, "tercero": 3, "cuarto": 4,
    "quinto": 5, "sexto": 6, "septimo": 7, "octavo": 8, "noveno": 9, "decimo": 10,
    "undecimo": 11, "duodecimo": 12,
}
_TILDES = str.maketrans("áéíóúÁÉÍÓÚ", "aeiouAEIOU")
_TERMINO = re.compile(r"^(" + "|".join(_ORDINAL) + r")\s+(?:y\s+\w+\s+)?cuatrimestre$")
_TERMINO_NUMERO = re.compile(r"^(\d{1,2})\s*(?:°|º|er|do|ro|to|vo|mo|no)?\s+cuatrimestre$")
_CBC = re.compile(r"^ciclo basico comun")
_CODIGO = re.compile(r"^\d{2}$")
_CREDITOS = re.compile(r"^\d+(?: de \d+)?$")
_FIN = re.compile(r"^total (creditos|horas|materias) del plan|^total materias|"
                  r"^total del \S+ ciclo|^total de la carrera|^total de (creditos|asignaturas)\b.*\bdel plan|"
                  r"^totales del|^asignaturas electivas")
# A term's subtotal: what follows it is the next term's, even when the
# document leaves out that term's heading (Bioingeniería's "QUINTO").
_SUBTOTAL = re.compile(r"^total\b")
_NO_ES_MATERIA = re.compile(
    r"^(total|ó|o|electivas?(/optativas?)?|optativas?|asignaturas|carga horaria)\b", re.I)


def _plano(texto: str) -> str:
    return " ".join(texto.translate(_TILDES).lower().split())


def leer_filas(filas: Iterable[list[str | None]]) -> list[tuple[str, int]]:
    """(subject, year) for each compulsory subject, from the rows of the
    plan's tables in the order of the document.

    Only the first run of terms is read, and it ends at the plan's total:
    what comes after (electives, equivalences with the old plan, the
    transition rules) repeats subject names that are not this plan's.
    """
    materias: list[tuple[str, int]] = []
    vistas: set[str] = set()
    anio: int | None = None
    ultimo_termino = 0
    en_cbc = False
    # The row after a subject's is its hours; a row after that with text only
    # in the name's column is the rest of a name too long for its cell.
    continuable = False
    tras_subtotal = False

    for fila in filas:
        celdas = [" ".join((c or "").split()) for c in fila]
        llenas = [c for c in celdas if c]
        if not llenas:
            continue
        primera = _plano(llenas[0])
        if _CBC.match(primera):
            en_cbc, anio, continuable = True, 1, False
            continue
        termino = _TERMINO.match(primera) or _TERMINO_NUMERO.match(primera)
        if termino:
            numero = termino.group(1)
            n = int(numero) if numero.isdigit() else _ORDINAL[numero]
            if en_cbc and n <= 2:
                # "Primer y segundo cuatrimestre", under the CBC's heading.
                continue
            if n <= ultimo_termino:
                break
            ultimo_termino = n
            en_cbc, anio, continuable, tras_subtotal = False, (n + 1) // 2, False, False
            continue
        if anio is None:
            continue
        if _FIN.match(primera):
            if ultimo_termino:
                break
            anio, en_cbc = None, False
            continue
        if _SUBTOTAL.match(primera):
            tras_subtotal = bool(ultimo_termino)
            continuable = False
            continue

        if en_cbc:
            if len(llenas) >= 2 and _CODIGO.match(llenas[0]):
                _agregar(materias, vistas, llenas[1], anio)
            elif len(llenas) >= 2 and _CREDITOS.match(llenas[1]):
                # Energía Eléctrica lists the CBC without the codes.
                _agregar(materias, vistas, llenas[0], anio)
            continue
        if len(llenas) >= 2 and _CREDITOS.match(llenas[1]) and re.search(r"[^\W\d]", llenas[0]):
            if tras_subtotal:
                ultimo_termino += 1
                anio, tras_subtotal = (ultimo_termino + 1) // 2, False
            continuable = _agregar(materias, vistas, llenas[0], anio)
            continue
        if len(llenas) == 1 and _CREDITOS.match(llenas[0]):
            continue  # the hours, on a row of their own
        if (continuable and celdas[0] and len(llenas) == 1 and materias
                and not _NO_ES_MATERIA.match(celdas[0])):
            nombre, cursada = materias[-1]
            vistas.discard(_plano(nombre))
            materias[-1] = (f"{nombre} {celdas[0]}", cursada)
            vistas.add(_plano(materias[-1][0]))
        continuable = False
    return materias


# A column heading caught in a wrapped name's cell: "Introducción a la
# Ingeniería Mecánica CRÉDITOS (carga".
_ENCABEZADO_PEGADO = re.compile(r"\s+(CR[ÉE]DITOS|HORAS|CORRELATIVAS)\b.*$")


def _agregar(materias: list[tuple[str, int]], vistas: set[str], nombre: str,
             anio: int) -> bool:
    nombre = _ENCABEZADO_PEGADO.sub("", nombre).strip()
    if _NO_ES_MATERIA.match(nombre) or _plano(nombre) in vistas:
        return False
    vistas.add(_plano(nombre))
    materias.append((nombre, anio))
    return True


def leer_pdf(ruta: str) -> list[tuple[str, int]]:
    import pdfplumber

    with pdfplumber.open(ruta) as pdf:
        filas = [fila for pagina in pdf.pages for tabla in pagina.extract_tables()
                 for fila in tabla]
    return leer_filas(filas)
