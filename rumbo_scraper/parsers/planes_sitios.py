"""The plan of studies as some universities lay it out on the career's page.

Each reader returns ``[(subject, year)]`` in the order the page gives them,
or an empty list when the page does not have the plan the way it expects;
`database.planes_documentos` checks that what comes out is the whole plan.

- UPC: an accordion per year ("Primer año"), the subjects as bullets.
- UNS: ``servicios.uns.edu.ar/grado/plan.asp``: a one-row table per subject
  ("9001 INTRODUCCION AL DERECHO | 64hs. | ..."), a one-cell table per year
  ("PRIMER AÑO"), and the electives after "MATERIAS OPTATIVAS".
- UNICEN: the "Plan de estudios" section, a heading per year ("Primer Año:")
  and the subjects as bullets or paragraphs.
- UNPSJB: a table whose year cell spans the year's rows ("PRIMERO"), or a
  table per year after its heading ("1° Año"), or year rows inside the table.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

from rumbo_scraper.normalizers.text import clean_text

_ORDINALES = {"primer": 1, "primero": 1, "segundo": 2, "tercer": 3, "tercero": 3, "cuarto": 4,
              "quinto": 5, "sexto": 6}
_ANIO = re.compile(r"(?i)^\s*(primer|primero|segundo|tercer|tercero|cuarto|quinto|sexto)\s*(?:a[ñn]o)?\s*:?\s*$")
_ANIO_NUMERO = re.compile(r"(?i)^\s*(\d)\s*[°ºo]?\s*a[ñn]o\s*:?\s*$")
# Not subjects: an elective's slot, a heading that ends in a colon.
_NO_ES_MATERIA = re.compile(
    r"(?i)^(?:asignaturas?\s+|materias?\s+)?(?:optativas?|electivas?|seminario optativo)(?:\s+(?:[ivx]+|\d+|optativas?|electivas?))*$"
    r"|:$|^resoluci[óo]n|deber[áa]|^entre\s+\d|a determinar|^horas flexibles$")


def _texto(elemento: Tag | None) -> str:
    return clean_text(elemento.get_text(" ")).replace("\xa0", " ").strip() if elemento else ""


def desde_el_primero(materias: list[tuple[str, int]]) -> list[tuple[str, int]]:
    """A plan whose first year, or any year between, is missing is not the
    whole plan."""
    anios = {a for _, a in materias}
    return materias if anios and anios == set(range(1, max(anios) + 1)) else []


def anio_de(texto: str) -> int | None:
    """"Primer año", "PRIMERO", "1° Año", "Segundo Año:" -> the year."""
    texto = clean_text(texto).replace("\xa0", " ")
    ordinal = _ANIO.match(texto)
    if ordinal:
        return _ORDINALES[ordinal.group(1).lower()]
    numero = _ANIO_NUMERO.match(texto)
    return int(numero.group(1)) if numero else None


def _agregar(materias: list[tuple[str, int]], nombre: str, anio: int | None) -> None:
    nombre = clean_text(nombre).replace("\xa0", " ").strip(" .;-–*")
    # "Algebra I (anual)", "Rítmica (Cuatr.)": how long it runs, not its name.
    nombre = re.sub(r"(?i)\s*\((?:anual|cuatrimestral|semestral|cuatr\.?|\d\s*[°º]?\s*cuatr\.?)\)\s*$", "", nombre)
    if nombre.isupper():
        from rumbo_scraper.parsers.guias_nacionales import con_tildes

        nombre = con_tildes(nombre)
    # "Anatomía Ii": the numeral of a subject's part is written in capitals.
    nombre = re.sub(r"(?i)\b(i{1,3}|iv|vi{0,3}|ix|x)\b(?=\s*$|\s*[:(-])", lambda m: m.group(1).upper(), nombre)
    nombre = re.sub(r"\s+", " ", nombre.replace("\u200b", "")).strip()
    if len(re.findall(r"[^\W\d_]", nombre)) < 3:
        return
    # A sentence ("El alumno debe aprobar 2 asignaturas electivas...") is a
    # rule of the plan, not a subject.
    if len(nombre.split()) > 14 or re.search(r"(?i)\bdebe\b|\bpromovido\b", nombre):
        return
    if anio and nombre and len(nombre) <= 150 and not _NO_ES_MATERIA.search(nombre) \
            and (nombre, anio) not in materias:
        materias.append((nombre, anio))


def _plan_upc(html: str) -> list[tuple[str, int]]:
    materias: list[tuple[str, int]] = []
    for item in BeautifulSoup(html or "", "html.parser").select(".jet-accordion__item"):
        anio = anio_de(_texto(item.select_one(".jet-toggle__label-text")).lower().replace("año", "").strip() + " año")
        for li in item.select(".jet-toggle__content li"):
            _agregar(materias, _texto(li), anio)
    return materias


_MATERIA_UNS = re.compile(r"^(\d{3,6})\s+(.+)$")
_ANIO_UNS = re.compile(r"(?i)^(primer|segundo|tercer|cuarto|quinto|sexto) a[ñn]o$|a[ñn]os?\s+(\d)\s*[ºo°]")


def _plan_uns(html: str) -> list[tuple[str, int]]:
    materias: list[tuple[str, int]] = []
    anio = None
    for tabla in BeautifulSoup(html or "", "html.parser").find_all("table"):
        if tabla.find("table"):
            continue
        for fila in tabla.find_all("tr"):
            celdas = [_texto(td) for td in fila.find_all(["td", "th"])]
            celdas = [c for c in celdas if c] or [""]
            if len(celdas) == 1:
                # The electives listed after a year are a pool, not that
                # year's subjects: skipped until the next year's heading.
                # ("G2347 Optativa de Abogacía" is an elective's slot in its
                # year: a row to skip, not the pool.)
                if re.search(r"(?i)optativa", celdas[0]):
                    if not re.match(r"^[A-Z]{0,2}\d{3,6}\s", celdas[0]):
                        anio = None
                    continue
                encabezado = _ANIO_UNS.search(celdas[0])
                if encabezado:
                    anio = _ORDINALES.get((encabezado.group(1) or "").lower()) or int(encabezado.group(2))
                continue
            materia = _MATERIA_UNS.match(celdas[0])
            if materia and len(celdas) > 1 and "hs" in celdas[1].lower():
                _agregar(materias, materia.group(2), anio)
    return materias


def _plan_unicen(html: str) -> list[tuple[str, int]]:
    soup = BeautifulSoup(html or "", "html.parser")
    seccion = next((s for s in soup.select("div.seccion-carrera")
                    if "plan de estudio" in _texto(s.select_one("h3.titulo")).lower()), None)
    cuerpo = seccion.select_one("div.cuerpo") if seccion else None
    if not cuerpo:
        return []
    materias: list[tuple[str, int]] = []
    anio = None
    for elemento in cuerpo.find_all(["h3", "h4", "p", "strong", "li"]):
        texto = _texto(elemento)
        nuevo = anio_de(texto)
        if nuevo:
            anio = nuevo
            continue
        # A module's sub-items (a list under the module's paragraph, or
        # inside its bullet) are part of it, not subjects of their own.
        if elemento.name == "li":
            lista = elemento.find_parent(["ul", "ol"])
            previo = lista.find_previous_sibling() if lista else None
            if elemento.find_parent("li") or (previo is not None and previo.name == "p"
                                               and not anio_de(_texto(previo))):
                continue
        if elemento.name in ("p", "li") and not elemento.find(["ul", "ol"]) \
                and not re.match(r"(?i)^(ciclo|otros requisitos|requisitos)", texto):
            _agregar(materias, re.sub(r"\s*\((?:CB|CP|CO)\)$", "", texto), anio)
    return materias


def _plan_unpsjb(html: str) -> list[tuple[str, int]]:
    soup = BeautifulSoup(html or "", "html.parser")
    materias: list[tuple[str, int]] = []
    # FCN: Año | # | Código | Materia | ..., the year cell spanning its rows.
    tabla = soup.select_one("table.is-style-stripes")
    if tabla:
        encabezado = [_texto(c).lower() for c in tabla.find("tr").find_all(["th", "td"])]
        if "materia" in encabezado:
            columna = encabezado.index("materia")
            anio = None
            for fila in tabla.find_all("tr")[1:]:
                celdas = fila.find_all(["td", "th"])
                if len(celdas) == len(encabezado):
                    anio = anio_de(_texto(celdas[0])) or anio
                    nombre = _texto(celdas[columna])
                else:
                    nombre = _texto(celdas[columna - 1]) if len(celdas) >= columna else ""
                _agregar(materias, nombre, anio)
            return materias
    # FHCS: COD | ASIGNATURAS | ..., the years as rows of their own.
    for tabla in soup.select("table.advgb-table-frontend"):
        anio = None
        for fila in tabla.find_all("tr"):
            celdas = [_texto(c) for c in fila.find_all(["td", "th"])]
            llenas = [c for c in celdas if c]
            if len(llenas) == 1 and anio_de(llenas[0].replace("AÑO", "año")):
                anio = anio_de(llenas[0])
                continue
            if len(celdas) >= 2 and re.match(r"^\d", celdas[0]) and celdas[1]:
                _agregar(materias, celdas[1], anio)
        if materias:
            return materias
    # Ingeniería: a table per year, after its heading.
    for tabla in soup.find_all("table"):
        titulo = tabla.find_previous(["h2", "h3", "h4", "p", "strong"])
        anio = anio_de(_texto(titulo)) if titulo else None
        if not anio:
            continue
        for fila in tabla.find_all("tr"):
            celdas = [_texto(c) for c in fila.find_all(["td", "th"])]
            if len(celdas) >= 2 and re.match(r"^[A-Z]{0,3}\d{2,}", celdas[0]):
                _agregar(materias, celdas[1], anio)
    return materias


def plan_upc(html: str) -> list[tuple[str, int]]:
    return desde_el_primero(_plan_upc(html))


def plan_uns(html: str) -> list[tuple[str, int]]:
    return desde_el_primero(_plan_uns(html))


def plan_unicen(html: str) -> list[tuple[str, int]]:
    return desde_el_primero(_plan_unicen(html))


def plan_unpsjb(html: str) -> list[tuple[str, int]]:
    return desde_el_primero(_plan_unpsjb(html))


def _plan_unne(html: str) -> list[tuple[str, int]]:
    """Each UNNE faculty its own way: Exactas a heading per year
    (``div.encabezado``) over a table of terms; Económicas a fold per year
    ("1º AÑO") with the subjects numbered in bold; Medicina a heading per
    year and each subject's name after the heading "Materia:"."""
    soup = BeautifulSoup(html or "", "html.parser")
    materias: list[tuple[str, int]] = []
    encabezados = soup.select("div.encabezado")
    if encabezados:
        for encabezado in encabezados:
            anio = anio_de(_texto(encabezado))
            tabla = encabezado.find_next("table")
            for celda in (tabla.find_all("td") if tabla and anio else []):
                texto = _texto(celda)
                if celda.find("table") or not texto or re.search(r"(?i)cuatrimestre|anual", texto):
                    continue
                _agregar(materias, texto, anio)
        return materias
    pliegues = soup.select(".eael-accordion-list")
    if pliegues:
        for pliegue in pliegues:
            anio = anio_de(_texto(pliegue.select_one(".eael-accordion-tab-title")))
            for negrita in pliegue.select(".eael-accordion-content p strong"):
                numerada = re.match(r"^\d+\s*\.\s*(.+)$", _texto(negrita))
                if numerada and anio:
                    _agregar(materias, numerada.group(1), anio)
        return materias
    anio, sigue_materia, dentro = None, False, False
    for titulo in soup.select(".elementor-heading-title"):
        texto = _texto(titulo)
        if re.match(r"(?i)^materias a cursar$", texto):
            dentro = True
            continue
        if not dentro:
            continue
        nuevo = anio_de(texto)
        if nuevo:
            anio = nuevo
            continue
        if re.match(r"(?i)^materia:?$", texto):
            sigue_materia = True
            continue
        if sigue_materia:
            _agregar(materias, re.sub(r"(?i)\s*\((?:optativa|a partir de[^)]*)\)", "", texto)
                     if not re.search(r"(?i)\(optativa\)", texto) else "", anio)
            sigue_materia = False
    return materias


def plan_unne(html: str) -> list[tuple[str, int]]:
    return desde_el_primero(_plan_unne(html))


def _plan_tabla_con_anios(html: str) -> list[tuple[str, int]]:
    """Tables where a row of one cell says the year ("1° AÑO") and a header
    row names the column of the subjects ("Asignatura", "Materia"): the
    UNSE's plans. A yearly subject listed under both terms counts once."""
    soup = BeautifulSoup(html or "", "html.parser")
    materias: list[tuple[str, int]] = []
    anio, columna = None, None
    for tabla in soup.find_all("table"):
        if tabla.find("table"):
            continue
        # Or the year is the text just before the table ("PRIMER AÑO", the
        # UNT's Artes).
        antes = tabla.find_previous(string=lambda t: t and t.strip())
        anio = anio_de(antes) if antes and anio_de(antes) else anio
        for fila in tabla.find_all("tr"):
            celdas = [_texto(c) for c in fila.find_all(["td", "th"])]
            llenas = [c for c in celdas if c]
            if len(llenas) == 1:
                anio = anio_de(llenas[0]) or anio
                continue
            nombres = [c.lower() for c in celdas]
            titulo = next((i for i, c in enumerate(nombres) if c in ("asignatura", "asignaturas", "materia", "materias")), None)
            if titulo is not None:
                columna = titulo
                continue
            if anio and columna is not None and len(celdas) > columna and celdas[0]:
                _agregar(materias, celdas[columna], anio)
    return materias


def plan_tabla_con_anios(html: str) -> list[tuple[str, int]]:
    return desde_el_primero(_plan_tabla_con_anios(html))


def _plan_fcyt_uader(html: str) -> list[tuple[str, int]]:
    """UADER's Ciencia y Tecnología: a fold per year, a table of subjects in it."""
    materias: list[tuple[str, int]] = []
    for panel in BeautifulSoup(html or "", "html.parser").select("div.vc_tta-panel"):
        anio = anio_de(_texto(panel.select_one(".vc_tta-title-text")))
        for fila in panel.select("table tr"):
            celdas = [_texto(c) for c in fila.find_all(["td", "th"])]
            if anio and celdas and celdas[0].lower() not in ("asignatura", "asignaturas"):
                _agregar(materias, celdas[0], anio)
    return materias


def plan_fcyt_uader(html: str) -> list[tuple[str, int]]:
    return desde_el_primero(_plan_fcyt_uader(html))


def plan_uncoma(html: str) -> list[tuple[str, int | None]]:
    """The Comahue lists a career's subjects under the heading "Materias",
    numbered ("1- TEORÍA GENERAL DEL DERECHO"), most without the year; some
    under "PRIMER AÑO – PRIMER CUATRIMESTRE". The electives after
    "Optativas" and the notes after "Observación" are not the plan."""
    soup = BeautifulSoup(html or "", "html.parser")
    titulo = next((h for h in soup.find_all(["h2", "h3"]) if _texto(h).lower() == "materias"), None)
    widget = titulo.find_parent(class_="elementor-widget") if titulo else None
    lista = widget.find_next_sibling() if widget else None
    if not lista:
        return []
    renglones: list[tuple[str, int | None]] = []
    anio = None
    for linea in lista.get_text("\n").split("\n"):
        linea = clean_text(linea).replace("\xa0", " ")
        if not linea:
            continue
        if re.match(r"(?i)^(observaci[óo]n|optativas?|materias optativas|electivas)", linea):
            break
        nuevo = anio_de(re.split(r"\s+[–-]\s+", linea)[0])
        if nuevo:
            anio = nuevo
            continue
        if re.match(r"(?i)^ciclo\b", linea):
            continue
        nombre = re.sub(r"^\d+\s*[-–.)]?\s*", "", linea)
        nombre = nombre.replace("DELDERECHO", "DEL DERECHO")
        vacias: list[tuple[str, int]] = []
        _agregar(vacias, nombre, 1)
        if vacias and all(vacias[0][0] != n for n, _ in renglones):
            renglones.append((vacias[0][0], anio))
    if any(a for _, a in renglones):
        return renglones if all(renglones) and {a for _, a in renglones} == set(range(1, max(a for _, a in renglones) + 1)) else []
    return renglones


_COLUMNA_UCSE = 50


def plan_ucse(texto_con_columnas: str) -> list[tuple[str, int]]:
    """The UCSE's brochure, as ``pdftotext -layout`` lays it out: the plan
    in the left column after "PLAN DE ESTUDIOS", a year per heading
    ("Primer año") and a subject per bullet ("£ Derecho Romano"); a name
    that wraps goes on indented; the electives are in the right column."""
    materias: list[tuple[str, int]] = []
    renglones: list[list] = []
    anio, dentro = None, False
    for linea in (texto_con_columnas or "").splitlines():
        if "PLAN DE ESTUDIOS" in linea:
            dentro = True
            continue
        if not dentro:
            continue
        izquierda = linea[:_COLUMNA_UCSE].rstrip()
        texto = clean_text(izquierda)
        if not texto:
            continue
        if re.match(r"(?i)^(alcances|optativa|perfil|t[íi]tulo|duraci[óo]n)", texto):
            if anio:
                break
            continue
        nuevo = anio_de(texto)
        if nuevo:
            anio = nuevo
            continue
        if texto.startswith("£") and anio:
            renglones.append([texto.lstrip("£ ").strip(), anio])
        elif izquierda.startswith("  ") and renglones and renglones[-1][1] == anio:
            renglones[-1][0] += " " + texto
    for nombre, anio_ in renglones:
        # The brochure's "fi" ligature comes out split: "Áf rica", "suf iciente".
        _agregar(materias, re.sub(r"(?<=\w)f (?=[a-záéíóúñ]{2,})", "f", nombre), anio_)
    return desde_el_primero(materias)


def _plan_en_lista(html: str) -> list[tuple[str, int]]:
    """A page whose content is the plan as plain lines: a year ("1º Año")
    and its subjects one per line, until the electives (the FACET's
    "Programas de materias")."""
    soup = BeautifulSoup(html or "", "html.parser")
    for parte in soup.find_all(["script", "style", "nav", "header", "footer", "aside"]):
        parte.decompose()
    contenido = soup.find("article") or soup.find("main") or soup
    materias: list[tuple[str, int]] = []
    anio = None
    for linea in contenido.get_text("\n").split("\n"):
        linea = clean_text(linea)
        if not linea:
            continue
        if re.match(r"(?i)^(materias|espacios)?\s*(optativ|electiv)", linea):
            break
        nuevo = anio_de(linea)
        if nuevo:
            anio = nuevo
            continue
        if anio:
            _agregar(materias, linea, anio)
    return materias


def plan_en_lista(html: str) -> list[tuple[str, int]]:
    return desde_el_primero(_plan_en_lista(html))
