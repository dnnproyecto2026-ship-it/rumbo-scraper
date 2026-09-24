"""The subjects of a plan that says how many each of its cycles has.

Ciencia Política at the UBA writes its plan as cycles, each announced with its
count and followed by its subjects, one per line:

    Ciclo General: Veintidós (22) asignaturas.
    Fundamentos de Ciencia Política I
    Teoría Política y Social I
    ...

The count is the check: a cycle is taken only when exactly that many subject
lines follow it. A cycle whose subjects are not listed ("Ciclo Orientado: Cinco
(5) materias. Dos (2) materias electivas a elegir...") gives nothing, and so
does a heading repeated in a summary above the lists. The page does not say
in which year each subject is taught, so none is given.
"""

from __future__ import annotations

import re

from rumbo_scraper.normalizers.text import clean_text
from rumbo_scraper.parsers.generico import es_materia

# "Ciclo General: Veintidós (22) asignaturas.", "Seis (6) materias", and in
# a table's heading row "Núcleo Básico Obligatorio: 12 asignaturas" (UNQ).
_ANUNCIO = re.compile(r"(?:\((\d{1,2})\)|:\s*(\d{1,2}))\s+(?:asignaturas|materias)\b", re.I)


def _es_una_materia(linea: str) -> bool:
    return es_materia(linea) and ":" not in linea and not _ANUNCIO.search(linea)


# A cycle of choices: its subjects are options, not the plan's.
_DE_ELECCION = re.compile(r"(?i)electiv|optativ|orientad|orientaci[oó]n|a elegir|elegir")


def leer(lineas: list[str]) -> list[str]:
    """The subjects of every cycle whose announced count its list matches.

    A compulsory cycle announced and not listed makes the whole unreadable:
    returning the other cycles would be a plan missing a part. A cycle of
    choices (electives, an orientation) is left out, and so is an
    announcement in a summary whose cycle is listed further down.
    """
    lineas = [clean_text(linea) for linea in lineas if clean_text(linea)]
    materias: list[str] = []
    faltantes: list[str] = []
    listados: set[str] = set()
    for i, linea in enumerate(lineas):
        anuncio = _ANUNCIO.search(linea)
        if not anuncio:
            continue
        cuantas = int(anuncio.group(1) or anuncio.group(2))
        ciclo = linea[:anuncio.start()].split(":")[0].strip().lower()
        siguiente = " ".join(lineas[i:i + 2])
        if _DE_ELECCION.search(siguiente):
            continue
        lista = lineas[i + 1:i + 1 + cuantas]
        if len(lista) == cuantas and all(_es_una_materia(m) for m in lista):
            materias += [m for m in lista if m not in materias]
            listados.add(ciclo)
        else:
            faltantes.append(ciclo)
    if any(ciclo not in listados for ciclo in faltantes):
        return []
    return materias


def leer_html(html: str) -> list[str]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html or "", "html.parser")
    for parte in soup.find_all(["nav", "header", "footer", "aside", "script", "style"]):
        parte.decompose()
    cuerpo = soup.find("main") or soup.body
    return leer(cuerpo.get_text("\n").split("\n")) if cuerpo else []


def leer_tablas_html(html: str) -> list[str]:
    """The same, over a page's tables: the first cell of each row is a line."""
    from rumbo_scraper.parsers.plan_por_columnas import tablas_html

    return leer([fila[0] for tabla in tablas_html(html) for fila in tabla if fila])
