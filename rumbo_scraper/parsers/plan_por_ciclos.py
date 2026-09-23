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

# "Ciclo General: Veintidós (22) asignaturas.", "Seis (6) materias".
_ANUNCIO = re.compile(r"\((\d{1,2})\)\s+(?:asignaturas|materias)\b", re.I)


def _es_una_materia(linea: str) -> bool:
    return es_materia(linea) and ":" not in linea and not _ANUNCIO.search(linea)


def leer(lineas: list[str]) -> list[str]:
    """The subjects of every cycle whose announced count its list matches."""
    lineas = [clean_text(linea) for linea in lineas if clean_text(linea)]
    materias: list[str] = []
    for i, linea in enumerate(lineas):
        anuncio = _ANUNCIO.search(linea)
        if not anuncio:
            continue
        cuantas = int(anuncio.group(1))
        lista = lineas[i + 1:i + 1 + cuantas]
        if len(lista) == cuantas and all(_es_una_materia(m) for m in lista):
            materias += [m for m in lista if m not in materias]
    return materias


def leer_html(html: str) -> list[str]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html or "", "html.parser")
    for parte in soup.find_all(["nav", "header", "footer", "aside", "script", "style"]):
        parte.decompose()
    cuerpo = soup.find("main") or soup.body
    return leer(cuerpo.get_text("\n").split("\n")) if cuerpo else []
