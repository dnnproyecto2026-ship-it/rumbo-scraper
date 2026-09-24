"""Whether what the catalogue says is what the university says.

Every row of the catalogue came from a university's site, read by a reader
that can be wrong: a heading taken for a subject, a list page taken for a
career, a name glued to the next one. The check goes back to the source and
asks three things, each on its own, and a row is verified only when all
three agree:

1. the source is the university's: its address is on the university's own
   domain (a subdomain counts: ``economicas.uba.ar`` is the UBA's), not a
   social network, a directory or another institution;
2. the source is still there: it answers, today;
3. the source says it: the career's page names the career, the plan names
   the subject, the profile names the person.

Nothing here decides what to do with a row that fails; it says why it
failed, and the catalogue shows the verified ones as such.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from rumbo_scraper.normalizers.text import clean_text, comparison_key

VERIFICADO = "verificado"
NO_LO_DICE = "no_lo_dice"
FUENTE_CAIDA = "fuente_caida"
FUENTE_NO_OFICIAL = "fuente_no_oficial"
SIN_FUENTE = "sin_fuente"

_SEGUNDO_NIVEL = frozenset({"edu", "com", "gob", "gov", "org", "net"})


def dominio(url: str | None) -> str:
    """The registrable domain of an address: ``fi.uba.ar`` is ``uba.ar``,
    ``www.unq.edu.ar`` is ``unq.edu.ar``."""
    host = urlparse(url or "").netloc.lower().split(":")[0].removeprefix("www.")
    partes = [p for p in host.split(".") if p]
    if len(partes) >= 3 and partes[-1] == "ar" and partes[-2] in _SEGUNDO_NIVEL:
        return ".".join(partes[-3:])
    return ".".join(partes[-2:])


def es_oficial(url: str | None, sitio_web: str | None) -> bool:
    return bool(url and sitio_web) and dominio(url) == dominio(sitio_web)


# A word the PDF broke at the end of a line: "Alimen- tos".
_PARTIDA = re.compile(r"(\w)-\s+(?=\w)")
_JSON_ESCAPE = re.compile(r"\\u([0-9a-fA-F]{4})")


# Where one cell of a table ends: a name matches within a cell, never
# running on into the next column's code ("Producción animal | CFE").
CORTE = "|"


def plano(texto: str | None) -> str:
    """The text as a run of plain words: no case, accents or punctuation,
    and the cell boundaries kept as ``|``."""
    texto = _PARTIDA.sub(r"\1", clean_text(texto or ""))
    return " ".join(re.findall(r"[a-z0-9]+|\|", comparison_key(texto)))


def texto_de_html(html: str) -> str:
    """All the page says, including what its scripts carry as data: a page
    built in the browser (Gatsby, Next) has its plan in a JSON blob."""
    soup = BeautifulSoup(html or "", "html.parser")
    datos = [s.string or "" for s in soup.find_all("script")]
    for parte in soup.find_all(["script", "style"]):
        parte.decompose()
    datos = [_JSON_ESCAPE.sub(lambda m: chr(int(m.group(1), 16)), d) for d in datos]
    return soup.get_text(" ") + " " + " ".join(datos)


def dice(fuente_plana: str, nombre: str | None) -> bool:
    """Whether the source, already made plain, has the name as whole words."""
    nombre = plano(nombre)
    return bool(nombre) and f" {nombre} " in f" {fuente_plana} "


_VACIAS = frozenset(
    "de del la las los el y e en a con para por o u al licenciatura licenciado licenciada "
    "tecnicatura tecnico tecnica universitaria universitario carrera ciclo profesorado "
    "profesor grado titulo".split())


def nombra_la_carrera(html: str, carrera: str) -> bool:
    """Whether the page is the career's: its title or main heading names it,
    or its content names every word of it that says something."""
    from rumbo_scraper.parsers.unidad import es_la_pagina_de

    if es_la_pagina_de(html, carrera):
        return True
    soup = BeautifulSoup(html or "", "html.parser")
    for parte in soup.find_all(["nav", "header", "footer", "aside", "script", "style"]):
        parte.decompose()
    palabras = set(plano(soup.get_text(" ")).split())
    propias = [p for p in plano(carrera).split() if p not in _VACIAS]
    return bool(propias) and all(p in palabras for p in propias)


_PARTICULAS = frozenset("de del la las los y van von da di dos das".split())


def nombra_a_la_persona(texto_plano: str, nombre: str) -> bool:
    """Whether the text has every word of the person's name ("Gareis,
    Rodolfo" on the page as "Rodolfo Gareis")."""
    palabras = set(texto_plano.split())
    propias = [p for p in plano(nombre).split() if p not in _PARTICULAS and len(p) > 1]
    return bool(propias) and all(p in palabras for p in propias)


def estado_de_la_fuente(url: str | None, sitio_web: str | None, respondio: bool) -> str | None:
    """What stops a source from verifying anything, or None when nothing does."""
    if not url:
        return SIN_FUENTE
    if not es_oficial(url, sitio_web):
        return FUENTE_NO_OFICIAL
    if not respondio:
        return FUENTE_CAIDA
    return None


# A code the reader glued to a subject from the table's next column: "CFE",
# "- DC", "C". A roman numeral is part of the name.
_CODIGO_PEGADO = re.compile(r"(?:\s+-?\s*(?!(?:[IVX]+)\b)[A-Z]{1,4})+\s*$")


def sin_codigo(nombre: str) -> str | None:
    """The name without the codes glued at its end, or None if it has none."""
    limpio = _CODIGO_PEGADO.sub("", nombre).strip(" -")
    return limpio if limpio and limpio != nombre.strip() else None


# At least this share of a plan found in one place makes that place its plan:
# the few missing are the reader's mistakes, not a source elsewhere.
PLAN_HALLADO = 0.5


def materias_del_plan(materias: list[str],
                      fuentes: dict[str, str]) -> dict[str, tuple[str, str | None, str | None]]:
    """For each subject of a career, its state, the source that says it and,
    when the source says it without a code the reader glued to it, the name
    as the source says it.

    ``fuentes`` maps each official source of the career (its page, the plan
    it links) to its plain text. When the sources together have at least
    half the plan, they are the plan, and a subject they do not have is one
    the plan does not say. When they have less, the plan was not found, and
    nothing can be said either way.
    """
    donde: dict[str, tuple[str | None, str | None]] = {}
    for materia in materias:
        url = next((u for u, texto in fuentes.items() if dice(texto, materia)), None)
        corregida = None
        if url is None and sin_codigo(materia):
            corregida = sin_codigo(materia)
            url = next((u for u, texto in fuentes.items() if dice(texto, corregida)), None)
        donde[materia] = (url, corregida if url else None)
    halladas = sum(1 for url, _ in donde.values() if url)
    falta = SIN_FUENTE if not materias or halladas < PLAN_HALLADO * len(materias) else NO_LO_DICE
    return {m: (VERIFICADO, url, corregida) if url else (falta, None, None)
            for m, (url, corregida) in donde.items()}
