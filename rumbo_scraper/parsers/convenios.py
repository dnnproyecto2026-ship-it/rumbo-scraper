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
    "botswana": "Botsuana", "botsuana": "Botsuana", "bulgaria": "Bulgaria",
    "emiratos arabes": "Emiratos Árabes Unidos", "emiratos arabes unidos": "Emiratos Árabes Unidos",
    "eslovenia": "Eslovenia", "eslovaquia": "Eslovaquia", "croacia": "Croacia",
    "serbia": "Serbia", "estonia": "Estonia", "letonia": "Letonia", "lituania": "Lituania",
    "ucrania": "Ucrania", "chipre": "Chipre", "malta": "Malta", "islandia": "Islandia",
    "luxemburgo": "Luxemburgo", "monaco": "Mónaco", "escocia ": "Reino Unido",
    "puerto rico": "Puerto Rico", "hong kong": "China", "macao": "China",
    "malasia": "Malasia", "libano": "Líbano", "jordania": "Jordania", "qatar": "Catar",
    "catar": "Catar", "arabia saudita": "Arabia Saudita", "kenia": "Kenia",
    "nigeria": "Nigeria", "ghana": "Ghana", "tunez": "Túnez", "argelia": "Argelia",
    "pakistan": "Pakistán", "bangladesh": "Bangladés", "sri lanka": "Sri Lanka",
    "nepal": "Nepal", "kazajistan": "Kazajistán", "mongolia": "Mongolia",
    "corea del norte": "Corea del Norte", "republica de corea": "Corea del Sur",
    "haiti": "Haití", "jamaica": "Jamaica", "trinidad y tobago": "Trinidad y Tobago",
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
        # The label is the last country named: "Universidad Autónoma
        # Metropolitana de los Estados Unidos Mexicanos – México" (Maimónides).
        paises = list(_UN_PAIS.finditer(comparison_key(texto)))
        pais = paises[-1] if paises else None
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


# ---------------------------------------------------------------- by country
#
# Many lists do not write the country beside each university: a heading with
# the country's name ("ALEMANIA", "Australia") stands over the universities
# of that country, one per line, or one per bullet when the list comes from a
# brochure. A double degree's list is left out: the lines under each of its
# universities are the careers it is for, not the rest of its name.

_UNA_INSTITUCION = re.compile(
    r"(?i:universi|college|coll[èe]ge|institut|school|[ée]cole|escuela|hochschule|"
    r"polit[ée]cni|polytechni|academ|akademi|conservatori|faculdade|facultad|"
    r"centro universitario|business)|\b[A-Z]{2,6}\b")
_SECCION = re.compile(r"(?i)^convenios? de (intercambio|doble t[íi]tulo|doble titulaci[óo]n)")


def pais_del_encabezado(linea: str) -> str | None:
    """The country a line names when the line is nothing but the country."""
    clave = comparison_key(clean_text(linea)).strip(" :.")
    return PAISES.get(clave) or PAISES.get(clave.replace(" ", " "))


def leer_por_pais(lineas: list[str], fuente: str, propia: str) -> list[dict[str, Any]]:
    """The universities a list gives under each country's heading.

    With bullets ("• Griffith University"), a line without one continues the
    name above it ("• Flinders University of South" / "Australia"); without
    bullets each line is a university. A line that names no institution ends
    the country's list, and so does a double degree's heading."""
    con_vinetas = sum(1 for linea in lineas if linea.lstrip().startswith("•")) >= 3
    clave_propia = comparison_key(propia)
    convenios: list[dict[str, Any]] = []
    vistas: set[str] = set()
    pais: str | None = None
    en_doble = False
    actual: list[str] = []

    def cerrar() -> None:
        if actual and pais and not en_doble:
            nombre = clean_text(" ".join(actual)).strip(" .,;-–")
            clave = comparison_key(nombre)
            if (6 <= len(nombre) <= 140 and pais != "Argentina" and clave not in vistas
                    and not (clave_propia and clave_propia in clave)):
                vistas.add(clave)
                convenios.append({"universidad_destino": nombre, "pais": pais, "ciudad": None,
                                  "programa": None, "fuente": fuente})
        actual.clear()

    for bruta in lineas:
        # A column's end: what runs on is the next column's, not this name's.
        if bruta == _OTRA_COLUMNA:
            cerrar()
            continue
        linea = clean_text(bruta)
        if not linea:
            continue
        nuevo = pais_del_encabezado(linea)
        # "• Flinders University of South" / "Australia": in a brochure the
        # headings are in capitals, and a country in a name's case goes on it.
        if nuevo and con_vinetas and actual and not linea.isupper():
            nuevo = None
        if nuevo:
            cerrar()
            pais, en_doble = nuevo, False
            continue
        seccion = _SECCION.match(linea)
        if seccion:
            cerrar()
            en_doble = not seccion.group(1).lower().startswith("intercambio")
            continue
        if not pais:
            continue
        if con_vinetas:
            if linea.startswith("•"):
                cerrar()
                actual.append(linea.lstrip("• ").strip())
            elif actual and not linea.isupper():
                actual.append(linea)
            continue
        # One university per line: a line naming no institution ends the list.
        if _UNA_INSTITUCION.search(linea) and len(linea) <= 110 and not linea.endswith("."):
            cerrar()
            actual.append(linea)
            cerrar()
        else:
            cerrar()
            pais = None
    cerrar()
    return convenios


def leer_json_ld(html: str, fuente: str) -> list[dict[str, Any]]:
    """The universities a page declares in its structured data as the ones it
    has agreements with (``CollegeOrUniversity`` items of an ``ItemList``).
    The page does not give their country."""
    import json

    convenios: list[dict[str, Any]] = []
    for bloque in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html or "", re.S):
        try:
            datos = json.loads(bloque)
        except ValueError:
            continue
        pila = [datos]
        while pila:
            nodo = pila.pop()
            if isinstance(nodo, list):
                pila.extend(nodo)
            elif isinstance(nodo, dict):
                if nodo.get("@type") == "ItemList" and re.search(
                        r"(?i)convenio|intercambio|vinculaci", f'{nodo.get("name", "")} {nodo.get("description", "")}'):
                    for item in nodo.get("itemListElement") or []:
                        cosa = (item or {}).get("item") or {}
                        if cosa.get("@type") == "CollegeOrUniversity" and cosa.get("name"):
                            convenios.append({"universidad_destino": clean_text(cosa["name"]), "pais": None,
                                              "ciudad": None, "programa": None, "fuente": fuente})
                else:
                    pila.extend(nodo.values())
    return convenios


_OTRA_COLUMNA = "\x00columna"


def lineas_por_columnas(pdf_path: str) -> list[str]:
    """A brochure's lines read column by column, each page's columns found
    where its bullets start ("•"), so a country's heading stays over its
    list (UB)."""
    import pdfplumber
    from collections import Counter

    lineas: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for pagina in pdf.pages:
            palabras = pagina.extract_words()
            comienzos = Counter(round(p["x0"] / 10) * 10 for p in palabras if p["text"] == "•")
            columnas: list[float] = []
            for x in sorted(x for x, veces in comienzos.items() if veces >= 2):
                if not columnas or x - columnas[-1] > 60:
                    columnas.append(x)
            bordes = [max(0, c - 8) for c in columnas] or [0]
            bordes.append(pagina.width)
            for i in range(len(bordes) - 1):
                texto = pagina.crop((bordes[i], 0, bordes[i + 1], pagina.height)).extract_text() or ""
                lineas += texto.split("\n") + [_OTRA_COLUMNA]
    return lineas


# UADE's brochure (``pdftotext -layout``): a country's heading ("    ALEMANIA")
# over a table "Universidad  Ciudad  Demanda  Áreas Sugeridas", a row per
# block of lines; a long name or city wraps within its column, above and
# below the row's middle line.
_TROZO = re.compile(r"\S+(?: \S+)*")


def leer_tabla_por_pais(texto_con_columnas: str, fuente: str, propia: str) -> list[dict[str, Any]]:
    """The universities a table gives under each country's heading, with the
    city in the column after the name; a row's pieces go to the column their
    start falls in, by the positions of the table's own heading."""
    clave_propia = comparison_key(propia)
    convenios: list[dict[str, Any]] = []
    vistas: set[str] = set()
    pais = None
    ciudad_desde = demanda_desde = None
    bloque: list[str] = []

    def cerrar() -> None:
        if pais and ciudad_desde is not None and bloque:
            nombre, ciudad = [], []
            for linea in bloque:
                for trozo in _TROZO.finditer(linea):
                    if trozo.start() < ciudad_desde - 2:
                        nombre.append(trozo.group())
                    elif demanda_desde is None or trozo.start() < demanda_desde - 2:
                        ciudad.append(trozo.group())
            texto = clean_text(" ".join(nombre))
            ciudad_texto = clean_text(" ".join(ciudad))
            clave = comparison_key(texto)
            # A section's heading, a note, the university's own addresses;
            # a row of several cities, whose wrap runs into the name's column
            # ("ISM - International School of Munich, Frankfurt, ...").
            if (re.match(r"(?i)convenios en|la oferta|uade\b", texto) or re.search(r"\d{4}", texto)
                    or texto.count(",") >= 2 or ciudad_texto.endswith(",")):
                bloque.clear()
                return
            if (texto and _UNA_INSTITUCION.search(texto) and pais != "Argentina" and clave not in vistas
                    and not (clave_propia and clave_propia in clave)):
                vistas.add(clave)
                convenios.append({"universidad_destino": texto, "pais": pais,
                                  "ciudad": ciudad_texto or None,
                                  "programa": None, "fuente": fuente})
        bloque.clear()

    for linea in (texto_con_columnas or "").splitlines():
        if not linea.strip():
            cerrar()
            continue
        nuevo = pais_del_encabezado(linea)
        if nuevo:
            cerrar()
            pais = nuevo
            continue
        if re.search(r"Universidad\s{2,}Ciudad", linea):
            cerrar()
            ciudad_desde, demanda_desde = linea.index("Ciudad"), (linea.index("Demanda") if "Demanda" in linea else None)
            continue
        bloque.append(linea)
    cerrar()
    return convenios
