"""How long a career takes, as its own page says it.

The pages say it in a handful of ways: "Duración: 5 años", "La carrera tiene
una duración de cuatro años y medio", "Duración estimada: 10 cuatrimestres",
"5 años de duración". The phrase is read only where it names the duration
-- a "3 años" loose in the text is the intermediate title, the years of
accreditation or an anniversary -- and only in the page's own content, not
its menu or footer.

A page that states two different durations is left alone: a degree and its
intermediate title ("a los 3 años obtenés el título de técnico") are one
page, and which is the career's is a guess. Terms and semesters count as half
a year. Anything outside one and a half to seven years is not a duration.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from rumbo_scraper.normalizers.text import clean_text, comparison_key

_PALABRAS = {
    "un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6,
    "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12, "trece": 13,
    "catorce": 14,
}
_NUMERO = r"(\d{1,2}(?:[.,]\d)?|" + "|".join(_PALABRAS) + r")"
_MEDIO = r"(?:\s*(?:y\s+medio|½|1/2))?"
_UNIDAD = r"(anos|ano|cuatrimestres|semestres)"
_CALIFICA = r"(?:\s+(?:teorica|estimada|total|minima|prevista|aproximada|real|de\s+la\s+carrera|del\s+plan(?:\s+de\s+estudios?)?))*"

# "Duración: 5 años", "duración de la carrera es de 4 años y medio".
_DURACION_ES = re.compile(
    r"duracion" + _CALIFICA + r"\s*(?:es\s+de|de|:|es|=)?\s*(?:\(|\s)*" + _NUMERO + r"(" + _MEDIO
    + r")\s*" + _UNIDAD + r"(\s+y\s+medio)?")
# "5 años de duración".
_ANIOS_DE_DURACION = re.compile(
    _NUMERO + r"(" + _MEDIO + r")\s*" + _UNIDAD + r"(\s+y\s+medio)?\s+de\s+duracion")


def _valor(numero: str, medio: str, unidad: str, medio_despues: str | None) -> float | None:
    numero = numero.replace(",", ".")
    valor = float(numero) if numero[0].isdigit() else float(_PALABRAS[numero])
    if medio.strip() or medio_despues:
        valor += 0.5
    if unidad.startswith(("cuatrimestre", "semestre")):
        valor /= 2
    return valor if 1.5 <= valor <= 7 else None


def duraciones_en(texto: str) -> set[float]:
    plano = comparison_key(clean_text(texto))
    halladas = set()
    for patron in (_DURACION_ES, _ANIOS_DE_DURACION):
        for match in patron.finditer(plano):
            valor = _valor(*match.groups())
            if valor is not None:
                halladas.add(valor)
    return halladas


def duracion_de_la_pagina(html: str) -> float | None:
    """The one duration the page's content states, or None."""
    soup = BeautifulSoup(html or "", "html.parser")
    for parte in soup.find_all(["nav", "header", "footer", "aside", "script", "style"]):
        parte.decompose()
    cuerpo = soup.find("main") or soup.body
    if cuerpo is None:
        return None
    halladas = duraciones_en(cuerpo.get_text(" "))
    return halladas.pop() if len(halladas) == 1 else None
