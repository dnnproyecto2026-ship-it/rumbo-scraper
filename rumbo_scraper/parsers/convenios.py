"""Reading the universities abroad that a university sends its students to.

Every university with an exchange programme publishes the list of the ones it
has an agreement with, and publishes it the same way: the name of the
university and the country it is in, one per line or one per row of a table.

The country is what makes the line readable. A line that names a university
and no country is as likely to be a faculty of the university publishing it,
so only the pair is kept.
"""

from __future__ import annotations

import re
from typing import Any

from rumbo_scraper.normalizers.text import clean_text, comparison_key
from rumbo_scraper.parsers.generico import _lineas, _quitar_accesorios, _soup

# How a university is named in Spanish, Portuguese, English, French, Italian
# and German, which is where the agreements of an Argentine university go.
_UNA_UNIVERSIDAD = re.compile(
    r"(?i)^(universidad|universidade|universit[àéy]|universit[äa]t|university|"
    r"universiteit|uniwersytet|univerzita|instituto|institut|politecnico|"
    r"polit[ée]cnico|polytechnic|college|coll[èe]ge|escuela|school|"
    r"hochschule|fachhochschule|ecole|[ée]cole|pontificia|centro universitario)"
    r"\b")

# The countries an Argentine university signs with. A country name is a fact
# about the world, not a claim about the university, so naming them here does
# not put anything into the data that the page did not say.
PAISES: dict[str, str] = {
    "argentina": "Argentina", "brasil": "Brasil", "brazil": "Brasil",
    "chile": "Chile", "uruguay": "Uruguay", "paraguay": "Paraguay",
    "bolivia": "Bolivia", "peru": "Perú", "ecuador": "Ecuador",
    "colombia": "Colombia", "venezuela": "Venezuela", "mexico": "México",
    "costa rica": "Costa Rica", "panama": "Panamá", "cuba": "Cuba",
    "republica dominicana": "República Dominicana", "guatemala": "Guatemala",
    "honduras": "Honduras", "nicaragua": "Nicaragua", "el salvador": "El Salvador",
    "estados unidos": "Estados Unidos", "eeuu": "Estados Unidos",
    "united states": "Estados Unidos", "usa": "Estados Unidos",
    "canada": "Canadá", "espana": "España", "spain": "España",
    "francia": "Francia", "france": "Francia", "italia": "Italia",
    "italy": "Italia", "alemania": "Alemania", "germany": "Alemania",
    "reino unido": "Reino Unido", "united kingdom": "Reino Unido",
    "inglaterra": "Reino Unido", "escocia": "Reino Unido",
    "portugal": "Portugal", "belgica": "Bélgica", "belgium": "Bélgica",
    "paises bajos": "Países Bajos", "holanda": "Países Bajos",
    "netherlands": "Países Bajos", "suiza": "Suiza", "switzerland": "Suiza",
    "austria": "Austria", "suecia": "Suecia", "noruega": "Noruega",
    "dinamarca": "Dinamarca", "finlandia": "Finlandia", "irlanda": "Irlanda",
    "polonia": "Polonia", "republica checa": "República Checa",
    "hungria": "Hungría", "rumania": "Rumania", "grecia": "Grecia",
    "turquia": "Turquía", "rusia": "Rusia", "china": "China",
    "japon": "Japón", "japan": "Japón", "corea del sur": "Corea del Sur",
    "corea": "Corea del Sur", "india": "India", "australia": "Australia",
    "nueva zelanda": "Nueva Zelanda", "sudafrica": "Sudáfrica",
    "israel": "Israel", "marruecos": "Marruecos", "egipto": "Egipto",
    "taiwan": "Taiwán", "singapur": "Singapur", "tailandia": "Tailandia",
    "vietnam": "Vietnam", "indonesia": "Indonesia", "filipinas": "Filipinas",
}
_UN_PAIS = re.compile(
    r"(?i)\b(" + "|".join(sorted((re.escape(p) for p in PAISES), key=len, reverse=True))
    + r")\b")

# What the page prints beside the list and is not an agreement.
_NO_ES_UN_CONVENIO = re.compile(
    r"(?i)^(universidad(?:es)? de destino|universidad(?:es)? socias?|"
    r"convenios?|acuerdos?|listado|instituciones|destinos|"
    r"universidad(?:es)?$)")


def leer_convenios(html: str, pagina: str, propia: str) -> list[dict[str, Any]]:
    """Read the partner universities a page lists, with the country of each.

    The university publishing the page is skipped wherever it names itself,
    which it does in its own header and in the sentence that introduces the
    list.
    """
    soup = _soup(html)
    programa = programa_de_la_pagina(soup)
    for element in soup(["script", "style", "noscript", "nav", "footer",
                         "header", "form", "select"]):
        element.decompose()
    _quitar_accesorios(soup)

    clave_propia = comparison_key(propia)
    convenios: list[dict[str, Any]] = []
    vistas: set[str] = set()
    for linea in _lineas(soup) + _de_las_celdas(soup):
        texto = clean_text(linea)
        if not (10 <= len(texto) <= 120) or len(texto.split()) > 14:
            continue
        if not _UNA_UNIVERSIDAD.match(texto) or _NO_ES_UN_CONVENIO.match(texto):
            continue
        pais = _UN_PAIS.search(comparison_key(texto))
        if not pais:
            continue
        # An exchange is with a university abroad. What names Argentina on
        # these pages is the sentence that introduces the list or the title
        # of the page itself.
        if PAISES[pais.group(1).lower()] == "Argentina":
            continue
        nombre = _sin_el_pais(texto, pais.group(1))
        if len(nombre) < 8 or comparison_key(nombre) == clave_propia:
            continue
        if clave_propia and clave_propia in comparison_key(nombre):
            continue
        clave = comparison_key(nombre)
        if clave in vistas:
            continue
        vistas.add(clave)
        convenios.append({"universidad_destino": nombre,
                          "pais": PAISES[pais.group(1).lower()],
                          "programa": programa, "fuente": pagina})
    return convenios


def programa_de_la_pagina(soup: Any) -> str | None:
    """The programme a page lists its partners under, as the page names it.

    ``convenios_intercambio.programa_origen`` cannot be null. An adapter
    fills it with the career an agreement belongs to; a page of the whole
    university lists them under the name of its exchange programme, which is
    its own heading. A page that does not name itself gives nothing to put
    there, and its rows are left out rather than filed under a name the
    university never used.
    """
    for tag in ("h1", "h2"):
        for heading in soup.find_all(tag):
            texto = clean_text(heading.get_text(" ", strip=True))
            if 6 <= len(texto) <= 90 and not _UNA_UNIVERSIDAD.match(texto):
                return texto
    if soup.title:
        titulo = re.split(r"\s+[|–—-]\s+", clean_text(soup.title.get_text(" ", strip=True)))[0]
        if 6 <= len(titulo) <= 90:
            return titulo
    return None


def _de_las_celdas(soup: Any) -> list[str]:
    """A table publishes the university in one cell and the country in another."""
    filas: list[str] = []
    for fila in soup.find_all("tr"):
        celdas = [clean_text(c.get_text(" ", strip=True))
                  for c in fila.find_all(["td", "th"])]
        celdas = [c for c in celdas if c]
        if 2 <= len(celdas) <= 5:
            # The cells are joined with a separator, because that is what
            # they are: the country sits in a column of its own, and joined
            # with a bare space it reads as part of the university's name.
            filas.append(" | ".join(celdas))
    return filas


# The marks a page puts between the name and the country it appends.
_UNA_ETIQUETA = "([-–—,|/"


def _sin_el_pais(texto: str, pais: str) -> str:
    """The name of the university, with the country label taken off.

    Only a country the page appended after a bracket or a dash is removed. A
    country that is part of the name stays, because cutting it turns
    "Universidad Católica del Uruguay" into "Universidad Católica del".

    The search runs on the comparison key, where the accents are gone, and
    the position maps back to the original text: the key keeps the length of
    what it came from for the letters these names use.
    """
    texto = clean_text(texto)
    # The label is appended at the end, so it is the last mention that is cut:
    # "Universidad Católica de Costa Rica (Costa Rica)" names the country
    # twice, once as part of the name.
    indice = comparison_key(texto).rfind(pais.lower())
    if indice <= 0:
        return texto.strip(" .,-–—()[]|")
    antes = texto[:indice].rstrip()
    if not antes or antes[-1] not in _UNA_ETIQUETA:
        # The country is part of the name.
        return texto.strip(" .,-–—()[]|")
    return _cerrado(clean_text(antes[:-1]).strip(" .,-–—[]|"))


def _cerrado(nombre: str) -> str:
    """The name with a bracket the cut left open closed again, or dropped."""
    if nombre.count("(") > nombre.count(")"):
        return nombre + ")" if re.search(r"\([^)]{2,}$", nombre) else nombre.rstrip("( ")
    if nombre.count(")") > nombre.count("("):
        return nombre.rstrip(") ")
    return nombre.strip()
