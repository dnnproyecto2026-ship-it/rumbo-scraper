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
from collections import Counter

from bs4 import BeautifulSoup, Tag

from rumbo_scraper.normalizers.text import clean_text

_ORDINALES = {"primer": 1, "primero": 1, "segundo": 2, "tercer": 3, "tercero": 3, "cuarto": 4,
              "quinto": 5, "sexto": 6}
_ANIO = re.compile(r"(?i)^\s*(primer|primero|segundo|tercer|tercero|cuarto|quinto|sexto)\s*(?:a[ñn]o)?\s*:?\s*$")
# "1° Año", "1er AÑO", "2do. Año", "1.er AÑO"
_ANIO_NUMERO = re.compile(r"(?i)^\s*(\d)\s*\.?\s*(?:er|ro|do|to|vo|mo|[°ºo])?\s*\.?\s*a[ñn]o\s*:?\s*$")
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
    # "Algebra I (anual)", "Rítmica (Cuatr.)", "Proyecto I Anual", "Matemática 1°C",
    # "(1° Cuatrimestre)", "(Anual) Créditos 10.00": how long it runs, not its name.
    nombre = re.sub(r"(?i)\s*cr[ée]ditos\s*[\d.,]+\s*$", "", nombre)
    nombre = re.sub(r"(?i)\s*\((?:anual|cuatrimestral|semestral|cuatr\.?|\d\s*[°º]?\s*(?:cuatr\.?|cuatrimestre|c))\)\s*$", "", nombre)
    nombre = re.sub(r"(?i)\s+(?:anual|cuatrimestral|\d\s*[°º]\s*c)$", "", nombre)
    # (An acronym stays one: "TFG", "PPS".)
    if nombre.isupper() and len(nombre) > 5:
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


# UNR Veterinaria's table of prerequisites: a row per subject whose first
# cell is its code, the year first ("3.24.2": third year, subject 24, second
# term), the name next.
def plan_por_codigo(html: str) -> list[tuple[str, int]]:
    materias: list[tuple[str, int]] = []
    for fila in BeautifulSoup(html or "", "html.parser").find_all("tr"):
        celdas = [_texto(celda) for celda in fila.find_all(["td", "th"])]
        codigo = re.fullmatch(r"(\d)\.\d+\.\d", celdas[0]) if len(celdas) > 1 else None
        if codigo:
            _agregar(materias, celdas[1], int(codigo.group(1)))
    return desde_el_primero(materias)


# A resolution's annex as ``pdftotext -layout`` lays it out (UNR
# Odontología): a row per subject whose code starts with the year ("1.3.1",
# "2.7", "1.6.2."), the name next, then its term ("Anual", "Cuatrimestral");
# a name that wraps goes on under itself in the next line.
_FILA_CON_ANIO_EN_EL_CODIGO = re.compile(r"^(\s*)(\d)\.\d{1,2}(?:\.\d)?\.?\s+(\S.*?)\s{2,}(?:Anual|Cuatrimestral|Semestral|Bimestral)\b")


def plan_por_codigo_en_texto(texto_con_columnas: str) -> list[tuple[str, int]]:
    renglones: list[list] = []
    columna = None
    for linea in (texto_con_columnas or "").splitlines():
        fila = _FILA_CON_ANIO_EN_EL_CODIGO.match(linea)
        if fila:
            columna = fila.start(3)
            renglones.append([fila.group(3), int(fila.group(2))])
            continue
        sigue = linea[columna:].split("  ")[0].strip() if columna and len(linea) > columna else ""
        # (Only a name's piece sits in its column, with nothing before it.)
        if renglones and sigue and not linea[:columna].strip() and not re.match(r"(?i)subtotal", sigue):
            renglones[-1][0] += " " + sigue
        elif linea.strip():
            columna = None
    materias: list[tuple[str, int]] = []
    for nombre, anio in renglones:
        _agregar(materias, nombre, anio)
    return desde_el_primero(materias)


# The UCASAL links two kinds of plan it can be read from, as ``pdftotext
# -layout`` lays them out:
# - its brochure: an "AÑO" heading per year whose number is a drawing (the
#   years are counted), the subjects one per line, the first of each term
#   after "ANUAL", "1° SEM." or "2° SEM.";
# - its students' office's "PLAN DE ESTUDIO POR CARRERA": "1 PRIMER AÑO",
#   then "05 0000   FILOSOFÍA   3   1 Sem" per subject.
# Its "PLAN DE ESTUDIO Y CORRELATIVIDADES DETALLADAS" cuts every name at
# twenty letters ("TÉC.Y ESTRAT.DE ESTU"): not read.
_UCASAL_PERIODO = re.compile(r"^(?:ANUAL|\d\s*°\s*SEM\.?)\s+")
_UCASAL_FILA = re.compile(r"^\d{2}\s+\d{4}\s+(.+?)\s{2,}\d+\s+(?:\d\s*)?(?:Sem|Anual|ANUAL)")
_UCASAL_ABREVIADA = re.compile(r"[º°]|\w\.(?=\s*\w)|\w\.$")
_UCASAL_NO_ES = re.compile(r"(?i)^(prueba de suficiencia|plan de estudio|carrera|modalidad|plan\s+\d)|@|ucasal\.edu")


def plan_ucasal(texto_con_columnas: str) -> list[tuple[str, int]]:
    texto = texto_con_columnas or ""
    if "CORRELATIVIDADES DETALLADAS" in texto:
        return []
    materias: list[tuple[str, int]] = []
    anio = 0
    if "PLAN DE ESTUDIO POR CARRERA" in texto:
        for linea in texto.splitlines():
            # (The columns are told apart by their runs of spaces.)
            linea = linea.replace("\xa0", " ").strip()
            encabezado = re.match(r"^(\d)\s+(?:PRIMER|SEGUNDO|TERCER|CUARTO|QUINTO|SEXTO)\s+AÑO$", linea)
            if encabezado:
                anio = int(encabezado.group(1))
                continue
            fila = _UCASAL_FILA.match(linea)
            if fila and anio:
                _agregar(materias, fila.group(1), anio)
        # One subject per instrument ("Instrumento Principal I / Canto I
        # (Oboe)", "(Guitarra)", ...) is a choice, not the plan's sequence.
        variantes = Counter(re.sub(r"\s*\(.*", "", nombre) for nombre, _ in materias)
        if variantes and max(variantes.values()) > 2:
            return []
        return desde_el_primero(materias)
    # Each page repeats the heading ("CARRERA (46) LICENCIATURA" over "EN
    # CRIMINALÍSTICA") up to its first year.
    encabezado = False
    for linea in texto.splitlines():
        linea = clean_text(linea)
        # (Some brochures print the number: "4 AÑO".)
        rotulo = re.fullmatch(r"(?:(\d)\s*)?AÑO", linea)
        if rotulo:
            anio, encabezado = int(rotulo.group(1) or anio + 1), False
            continue
        if linea.startswith("PLAN DE ESTUDIO"):
            encabezado = True
        nombre = _UCASAL_PERIODO.sub("", linea)
        if encabezado or not anio or not nombre or _UCASAL_NO_ES.search(nombre):
            continue
        # Some brochures copy the students' office's short names ("Dº PROC
        # CIVIL I", "PSIC.DESARR.NIÑO Y A"): such a plan is not read at all.
        if _UCASAL_ABREVIADA.search(nombre) or len(nombre) == 20:
            return []
        if nombre.isupper():
            _agregar(materias, nombre, anio)
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


def _plan_tablas_por_anio(html: str) -> list[tuple[str, int]]:
    """A heading per year ("Primer Año") and, under it, a table of one
    subject per row (the UNR's Ciencia Política): a table under any other
    heading (electives, seminars) is not the plan."""
    materias: list[tuple[str, int]] = []
    for titulo in BeautifulSoup(html or "", "html.parser").find_all(["h2", "h3", "h4", "h5"]):
        anio = anio_de(_texto(titulo))
        tabla = titulo.find_next("table")
        siguiente = titulo.find_next(["h2", "h3", "h4", "h5"])
        if not anio or not tabla or (siguiente and siguiente.sourceline and tabla.sourceline
                                     and siguiente.sourceline < tabla.sourceline):
            continue
        for fila in tabla.find_all("tr"):
            celdas = [_texto(c) for c in fila.find_all(["td", "th"]) if _texto(c)]
            if celdas:
                _agregar(materias, celdas[0], anio)
    return materias


def plan_tablas_por_anio(html: str) -> list[tuple[str, int]]:
    return desde_el_primero(_plan_tablas_por_anio(html))


_INICIALES = re.compile(r"\s+(?!(?:I{1,3}|IV|VI{0,3}|IX|X)\b)(?:[A-Z]\.?){1,4}\.?$")


def _plan_upso(html: str) -> list[tuple[str, int]]:
    """UPSO: "PLAN DE ESTUDIOS", then each year ("PRIMER AÑO"), its terms and
    the subjects one per line, until the page's other sections. A subject
    shared by careers carries their initials ("Estadística DLR")."""
    soup = BeautifulSoup(html or "", "html.parser")
    contenido = soup.select_one(".entry-content") or soup.body or soup
    lineas = [clean_text(l) for l in contenido.get_text("\n").split("\n") if clean_text(l)]
    inicio = next((i for i, l in enumerate(lineas) if re.match(r"(?i)^plan de estudios?:?$", l)), None)
    if inicio is None:
        return []
    materias: list[tuple[str, int]] = []
    anio = None
    for linea in lineas[inicio + 1:]:
        nuevo = anio_de(linea)
        if nuevo:
            anio = nuevo
            continue
        if re.match(r"(?i)^([12]\s*[º°]|primer|segundo)\s*cuatrimestre", linea):
            continue
        if anio and (len(linea) > 90 or re.match(
                r"(?i)^(requisitos|inscrip|documentaci|informaci|condiciones|t[íi]tulo|alcances|perfil|"
                r"materias optativas|optativas|asignaturas optativas|preinscrip)", linea)):
            break
        if anio and not re.match(r"(?i)^prueba de suficiencia", linea):
            _agregar(materias, _INICIALES.sub("", linea), anio)
    return materias


def plan_upso(html: str) -> list[tuple[str, int]]:
    return desde_el_primero(_plan_upso(html))


_ANIO_EN = re.compile(r"(?i)(primer|segundo|tercer|cuarto|quinto|sexto)\s*a[ñn]o")
_PARTICULAS = {"a", "al", "de", "del", "la", "las", "los", "el", "y", "e", "en", "con", "para", "por", "o", "u"}


def _sin_mayuscula_en_cada_palabra(nombre: str) -> str:
    """"Introducción A Las Problemáticas Sociales Y Territoriales" -> "...a las ... y ..."."""
    palabras = nombre.split()
    if len(palabras) > 2 and all(p[:1].isupper() for p in palabras if p[:1].isalpha()):
        return " ".join(p.lower() if i and p.lower() in _PARTICULAS else p for i, p in enumerate(palabras))
    return nombre


def _plan_unvm(html: str) -> list[tuple[str, int]]:
    """UNVM, two layouts: Básicas' tabs, a year each ("PRIMER AÑO") over a
    table whose column "Espacios curriculares" names the subjects (the first
    grid is the plan in force); Sociales' and Humanas' boxes, a year heading
    and the subjects one per line. The "C.T.F.C. ... E.C.E." lines are elective
    credits, not subjects."""
    soup = BeautifulSoup(html or "", "html.parser")
    materias: list[tuple[str, int]] = []
    secciones = soup.select("section.av_tab_section")
    if secciones:
        pares = [par for seccion in secciones for par in zip(seccion.select(".tab"), seccion.select(".tab_content"))]
        vistos: set[int] = set()
        for pestania, contenido in pares:
            encontrado = _ANIO_EN.search(_texto(pestania))
            tabla = contenido.find("table")
            if not encontrado or not tabla:
                continue
            anio = _ORDINALES[encontrado.group(1).lower()]
            # A year again is the older plan's grid (Veterinaria's 2017 under its 2022).
            if anio in vistos:
                break
            vistos.add(anio)
            columna = None
            for fila in tabla.find_all("tr"):
                celdas = [_texto(c) for c in fila.find_all(["td", "th"])]
                if columna is None:
                    columna = next((i for i, c in enumerate(celdas) if re.match(r"(?i)espacios? curricular|asignatura|materia", c)), None)
                    continue
                if len(celdas) > columna and celdas[columna] and not re.match(r"(?i)^c\.?\s*t\.?\s*f\.?\s*c", celdas[columna]):
                    _agregar(materias, _sin_mayuscula_en_cada_palabra(celdas[columna]), anio)
        return materias
    for caja in soup.select(".et_pb_text_inner"):
        encabezado = caja.find(["h4", "h5"])
        encontrado = _ANIO_EN.search(_texto(encabezado)) if encabezado else None
        if not encontrado:
            continue
        anio = _ORDINALES[encontrado.group(1).lower()]
        encabezado.extract()
        # A subject per line of the box, the lines broken by <br> or
        # paragraphs; a name's inline markup is not a break.
        for salto in caja.find_all("br"):
            salto.replace_with("\n")
        for parrafo in caja.find_all(["p", "li", "div"]):
            parrafo.insert_after("\n")
        for linea in caja.get_text("").split("\n"):
            linea = clean_text(linea).lstrip("–- ")
            if linea and not re.search(r"(?i)c\.?\s*t\.?\s*f\.?\s*c|e\.?\s*c\.?\s*e\.|cuatrimestre", linea) \
                    and not _ANIO_EN.search(linea):
                _agregar(materias, _sin_mayuscula_en_cada_palabra(linea), anio)
    return materias


def plan_unvm(html: str) -> list[tuple[str, int]]:
    return desde_el_primero(_plan_unvm(html))


def _plan_ucalp(html: str) -> list[tuple[str, int]]:
    """UCALP, two layouts: its plan pages (/plan-de-estudio/<slug>/), a fold
    per year ("1er. Año") with each subject in a bullet's span; or a career
    page's "Plan de Estudios" section, a heading per year ("1er AÑO") and
    the subjects as bullets. "(A)", "(C)" say annual or by term."""
    soup = BeautifulSoup(html or "", "html.parser")
    materias: list[tuple[str, int]] = []
    paneles = soup.select("#plan-de-estudio .panel")
    if paneles:
        for panel in paneles:
            anio = anio_de(_texto(panel.select_one(".panel-heading")))
            for li in panel.select("li"):
                _agregar(materias, _texto(li.find("span") or li), anio)
        return materias
    titulo = next((h for h in soup.find_all("h2") if "plan de estudio" in _texto(h).lower()), None)
    anio = None
    for elemento in (titulo.find_all_next(["h2", "h4", "h5", "h6", "strong", "li"]) if titulo else []):
        if elemento.name == "h2":
            break
        texto = _texto(elemento)
        nuevo = anio_de(texto)
        if nuevo:
            anio = nuevo
        elif elemento.name == "li":
            _agregar(materias, re.sub(r"\s*\((?:A|C|\d)\)\s*$", "", texto), anio)
    return materias


def plan_ucalp(html: str) -> list[tuple[str, int]]:
    return desde_el_primero(_plan_ucalp(html))


def _plan_unlpam(html: str) -> list[tuple[str, int]]:
    """UNLPam, two faculties' layouts: Humanas' tab "Asignaturas", a bold row
    per year ("Primer Año") and a cell per subject beside its programme's
    link; Exactas' plan pages, a heading per year ("PRIMER AÑO"), a label
    per term and the subjects one per line, a resolution sometimes after
    one ("– (Res N° 110/2025 Dc.)")."""
    soup = BeautifulSoup(html or "", "html.parser")
    materias: list[tuple[str, int]] = []
    pestania = soup.select_one("#v-pills-asignaturas")
    if pestania:
        anio = None
        for celda in pestania.select("div.col-12, div.col-6"):
            texto = _texto(celda)
            if "col-12" in (celda.get("class") or []):
                anio = anio_de(texto)
            elif anio and not celda.find("a") and not re.match(r"(?i)^descargar", texto) \
                    and not re.match(r"(?i)^esp\. curricular|^espacio curricular", texto):
                _agregar(materias, texto, anio)
        return materias
    contenido = soup.select_one(".entry-content")
    anio = None
    for elemento in (contenido.find_all(["h4", "p"]) if contenido else []):
        texto = _texto(elemento)
        if elemento.name == "h4":
            anio = anio_de(texto.lstrip("*"))
            continue
        if not anio or not elemento.find("i", class_=re.compile("fa-file")):
            continue
        for salto in elemento.find_all("br"):
            salto.replace_with("\n")
        for linea in elemento.get_text("").split("\n"):
            linea = re.sub(r"\s*[–-]\s*\(?\s*res\.?\b.*$", "", clean_text(linea), flags=re.I)
            _agregar(materias, linea, anio)
    return materias


def plan_unlpam(html: str) -> list[tuple[str, int]]:
    return desde_el_primero(_plan_unlpam(html))


def _plan_list_group(html: str) -> list[tuple[str, int]]:
    """UNJu, Humanidades: a list per year, its first item the year ("Primer
    Año") and the subjects after it; the lists of electives or languages
    are not years."""
    materias: list[tuple[str, int]] = []
    for grupo in BeautifulSoup(html or "", "html.parser").select("div.list-group, ul.list-group"):
        items = grupo.select(".list-group-item")
        anio = anio_de(_texto(items[0])) if items else None
        for item in items[1:] if anio else []:
            _agregar(materias, _texto(item), anio)
    return materias


def plan_list_group(html: str) -> list[tuple[str, int]]:
    return desde_el_primero(_plan_list_group(html))


def _plan_exa_unsa(html: str) -> list[tuple[str, int]]:
    """UNSa, Exactas: the plan's table, a row per year ("Primer año") and a
    row per subject under it."""
    materias: list[tuple[str, int]] = []
    tabla = BeautifulSoup(html or "", "html.parser").select_one("table.exa-plan-table")
    anio = None
    for fila in tabla.select("tr") if tabla else []:
        if "exa-plan-yrow" in (fila.get("class") or []):
            anio = anio_de(_texto(fila))
            continue
        nombre = fila.select_one("td.exa-plan-tname")
        if anio and nombre:
            _agregar(materias, _texto(nombre), anio)
    return materias


def plan_exa_unsa(html: str) -> list[tuple[str, int]]:
    return desde_el_primero(_plan_exa_unsa(html))


_REGIMEN = re.compile(r"(?i)^(i{1,2}|a|anual|\d\s*°?\s*c(uat)?\.?)$")


def _plan_natura_unsa(html: str) -> list[tuple[str, int]]:
    """UNSa, Ciencias Naturales: a table per plan, a row per year ("Primer
    Año", alone or before the year's first subject) and a row per subject:
    number, name, its chair's contact (✉) and the term (I, II, A). A table
    with no year (the electives') is not the plan."""
    materias: list[tuple[str, int]] = []
    for tabla in BeautifulSoup(html or "", "html.parser").find_all("table"):
        anio = None
        for fila in tabla.find_all("tr"):
            celdas = [_texto(c) for c in fila.find_all(["td", "th"])]
            dicho = next((anio_de(c) for c in celdas if re.fullmatch(r"(?i)\w+\s+año", c) and anio_de(c)), None)
            if dicho:
                anio = dicho
                celdas = celdas[[i for i, c in enumerate(celdas) if anio_de(c) == dicho][0] + 1:]
            if len(celdas) == 1 and re.match(r"(?i)optativ|electiv", celdas[0]):
                anio = None
            celdas = [c for c in celdas if not c.startswith("✉")]
            if anio and len(celdas) >= 2 and _REGIMEN.match(celdas[-1]):
                _agregar(materias, celdas[-2], anio)
    return materias


def plan_natura_unsa(html: str) -> list[tuple[str, int]]:
    return desde_el_primero(_plan_natura_unsa(html))


def _plan_eco_unsa(html: str) -> list[tuple[str, int]]:
    """UNSa, Económicas: the plan's table, a row per year ("Primer Año") and
    per term, and a row per subject: its number, its kind (T, TP, P) and its
    name with the campuses giving it ("Contabilidad I - Sede Central - Sede
    Norte"). A parallel chair (no number) is not another subject."""
    materias: list[tuple[str, int]] = []
    tabla = BeautifulSoup(html or "", "html.parser").find("table")
    anio = None
    for fila in tabla.find_all("tr") if tabla else []:
        celdas = [_texto(c) for c in fila.find_all(["td", "th"])]
        if len(celdas) < 3:
            continue
        if not celdas[0] and re.fullmatch(r"(?i)\w+\s+año", celdas[2]):
            anio = anio_de(celdas[2])
        elif anio and re.fullmatch(r"\d{1,4}", celdas[0]) and not re.search(r"(?i)optativ|electiv", celdas[2]):
            _agregar(materias, re.sub(r"(?i)\s*-\s*sede\b.*$", "", celdas[2]), anio)
    return materias


def plan_eco_unsa(html: str) -> list[tuple[str, int]]:
    return desde_el_primero(_plan_eco_unsa(html))


def _plan_ing_unsa(html: str) -> list[tuple[str, int]]:
    """UNSa, Ingeniería: a row per year ("PRIMER AÑO") and a row per
    subject (code, term, name, area...). Another heading ("REQUISITOS
    CURRICULARES", "ELECTIVAS") ends the plan, and an elective's slot
    ("Electiva") is not a subject."""
    materias: list[tuple[str, int]] = []
    anio = None
    for tabla in BeautifulSoup(html or "", "html.parser").find_all("table"):
        for fila in tabla.find_all("tr"):
            celdas = [_texto(c) for c in fila.find_all(["td", "th"])]
            if len(celdas) == 1:
                anio = anio_de(celdas[0]) if re.fullmatch(r"(?i)\w+\s+año", celdas[0]) else None
            elif anio and len(celdas) >= 3 and re.fullmatch(r"\d{1,3}", celdas[0]) \
                    and not re.match(r"(?i)electiva|optativa", celdas[2]):
                _agregar(materias, celdas[2], anio)
    return materias


def plan_ing_unsa(html: str) -> list[tuple[str, int]]:
    return desde_el_primero(_plan_ing_unsa(html))


def _plan_filas_numeradas(html: str) -> list[tuple[str, int]]:
    """UNCA, Humanidades: a table with a row per year ("Primer año") and a
    row per subject, numbered in its first cell ("1. Introducción a la
    Filosofía") beside its programme. Another heading ends the year."""
    materias: list[tuple[str, int]] = []
    for tabla in BeautifulSoup(html or "", "html.parser").find_all("table"):
        anio = None
        for fila in tabla.find_all("tr"):
            celdas = [c for c in (_texto(c) for c in fila.find_all(["td", "th"])) if c]
            if len(celdas) == 1 and not re.match(r"\d+\s*[.)-]", celdas[0]):
                anio = anio_de(celdas[0]) if re.fullmatch(r"(?i)\w+\s+año", celdas[0]) else None
                continue
            numerada = re.match(r"\d{1,3}\s*[.)-]\s*(\S.*)", celdas[0]) if celdas else None
            if anio and numerada:
                _agregar(materias, numerada.group(1), anio)
    return materias


def plan_filas_numeradas(html: str) -> list[tuple[str, int]]:
    return desde_el_primero(_plan_filas_numeradas(html))


def _plan_cr_year(html: str) -> list[tuple[str, int]]:
    """UNLZ, Derecho: a fold per year ("Primer año"), a line per subject in
    it: its number, its name and its hours ("<b>1.</b> Introducción al
    Derecho <span>· 48 hs</span>")."""
    materias: list[tuple[str, int]] = []
    for pliegue in BeautifulSoup(html or "", "html.parser").select("details.cr-year"):
        anio = anio_de(_texto(pliegue.find("summary")))
        for linea in pliegue.select(".cr-materia") if anio else []:
            for aparte in linea.find_all(["b", "span"]):
                aparte.decompose()
            _agregar(materias, _texto(linea), anio)
    return materias


def plan_cr_year(html: str) -> list[tuple[str, int]]:
    return desde_el_primero(_plan_cr_year(html))


def _plan_anio_y_lista(html: str) -> list[tuple[str, int]]:
    """UNaM, Humanidades: a table whose rows alternate a year ("PRIMER
    AÑO") and a list of its subjects. An elective's slot ("Asignatura
    Optativa") is not a subject."""
    materias: list[tuple[str, int]] = []
    for tabla in BeautifulSoup(html or "", "html.parser").find_all("table"):
        anio = None
        for fila in tabla.find_all("tr"):
            items = fila.find_all("li")
            if not items:
                texto = _texto(fila)
                anio = anio_de(texto) if re.fullmatch(r"(?i)\w+\s+año", texto) else None
                continue
            for item in items if anio else []:
                if not re.search(r"(?i)optativ|electiv", _texto(item)):
                    _agregar(materias, _texto(item), anio)
    return materias


def plan_anio_y_lista(html: str) -> list[tuple[str, int]]:
    return desde_el_primero(_plan_anio_y_lista(html))


def _plan_fce_unam(html: str) -> list[tuple[str, int]]:
    """UNaM, Económicas: a fold per plan ("Plan de estudios 2020"), the
    newest the career's, or the plan alone; in it, a heading per year ("Segundo Año") and a
    row per subject: its name, its code (CR201) and its term. An elective's
    credit ("Crédito para Optativas") is not a subject."""
    soup = BeautifulSoup(html or "", "html.parser")
    pliegues = [(int(re.search(r"20\d\d", _texto(t)).group()), t) for t in soup.select(".elementor-tab-title")
                if re.fullmatch(r"(?i)plan de estudios? (20\d\d)", _texto(t))]
    if pliegues:
        contenido = max(pliegues, key=lambda p: p[0])[1].find_next_sibling("div")
    else:
        # A career with one plan shows it without a fold.
        for parte in soup.find_all(["script", "style", "nav", "header", "footer", "aside"]):
            parte.decompose()
        contenido = soup.find("article") or soup.find("main") or soup.body
    materias: list[tuple[str, int]] = []
    anio, anterior = None, ""
    for linea in (clean_text(l) for l in (contenido.get_text("\n") if contenido else "").split("\n")):
        if not linea:
            continue
        # The language tests after the plan ("Requisitos extracurriculares").
        if re.match(r"(?i)requisitos", linea):
            break
        if re.fullmatch(r"(?i)\w+\s+año", linea) and anio_de(linea):
            anio = anio_de(linea)
        elif anio and re.fullmatch(r"[A-Z]{1,3}\d{3}", linea) and not re.search(r"(?i)optativ|electiv", anterior):
            _agregar(materias, anterior, anio)
        anterior = linea
    return materias


def plan_fce_unam(html: str) -> list[tuple[str, int]]:
    return desde_el_primero(_plan_fce_unam(html))


# The term may be on the line above ("1ºC" over "IC411   SISTEMAS DIGITALES");
# the code is in the first column (a code far right is a correlative).
_FILA_CON_CODIGO = re.compile(
    r"^\s{0,12}[A-Z]{2,3}\d{3}\s+(?:(?:ANUAL|\d\s*[º°o]\s*C\.?|\d\s*[º°o]\s*CUAT\S*)\s+)?([A-ZÁÉÍÓÚÑ]\S*.*?)(?:\s{2,}|$)")


def _plan_fio_unam(texto: str) -> list[tuple[str, int]]:
    """UNaM, Ingeniería: the plan's PDF as ``pdftotext -layout`` gives it, a
    heading per year ("SEGUNDO AÑO") and a row per subject: its code, its
    term and its name ("CI211   1º C.   CÁLCULO 2"). The code does not give
    the year (Probabilidad, CI213, is in the third)."""
    materias: list[tuple[str, int]] = []
    anio = None
    for linea in texto.split("\n"):
        limpia = clean_text(linea)
        if re.fullmatch(r"(?i)\w+\s+año", limpia):
            anio = anio_de(limpia)
            continue
        if re.match(r"(?i)(asignaturas\s+)?(optativ|electiv)", limpia):
            anio = None
        fila = _FILA_CON_CODIGO.match(linea)
        if anio and fila:
            # A row whose name went to another line leaves its correlatives
            # ("EM111-EM112") where the name was: the plan read so would
            # miss that subject, and is not read.
            if re.match(r"[A-Z]{2,3}\d{3}\b", fila.group(1)):
                return []
            _agregar(materias, fila.group(1), anio)
    return materias


def plan_fio_unam(texto: str) -> list[tuple[str, int]]:
    return desde_el_primero(_plan_fio_unam(texto))


def _plan_unq(html: str) -> list[tuple[str, None]]:
    """UNQ: a plan of credits, without years: a table with a row per
    núcleo that says how many subjects it has ("Núcleo Básico Obligatorio:
    12 asignaturas") and a row per subject after it. The obligatory núcleos
    are the plan; the elective and oriented ones are pools to choose from.
    A núcleo whose rows are not the number it says is not read, nor the
    plan."""
    materias: list[tuple[str, None]] = []
    tabla = BeautifulSoup(html or "", "html.parser").find("table")
    nucleos: list[tuple[int | None, list[str]]] = []
    obligatorio = False
    for fila in tabla.find_all("tr") if tabla else []:
        celdas = [_texto(c) for c in fila.find_all(["td", "th"])]
        if not celdas or not celdas[0]:
            continue
        if not any(celdas[1:]) and re.match(r"(?i)(n[úu]cleo|ciclo|trayecto|[áa]rea)\b", celdas[0]):
            obligatorio = bool(re.search(r"(?i)obligatori", celdas[0]))
            cuantas = re.search(r"(\d+)\s+asignaturas", celdas[0], re.I)
            if obligatorio:
                nucleos.append((int(cuantas.group(1)) if cuantas else None, []))
            continue
        if obligatorio and any(celdas[1:]):
            nucleos[-1][1].append(celdas[0])
    leidas: list[tuple[str, int]] = []
    for cuantas, nombres in nucleos:
        if cuantas is None or cuantas != len(nombres):
            return []
        for nombre in nombres:
            # (_agregar keeps a subject with its year; these have none.)
            _agregar(leidas, nombre, -1)
    materias += [(nombre, None) for nombre, _ in leidas]
    return materias


def plan_unq(html: str) -> list[tuple[str, None]]:
    return _plan_unq(html)


def _plan_titulo_y_lista(html: str) -> list[tuple[str, int]]:
    """UNC, Lenguas: a line in bold per year ("Primer año") and a list of
    its subjects after it; a subject taught by two chairs is one ("Lengua
    Inglesa I: Cátedra A - Cátedra B"), an optional one is not in the plan
    ("Lengua y Cultura Latina I (Optativa)"). Another bold line ("Ciclo de
    nivelación", "Seminarios") is not a year."""
    materias: list[tuple[str, int]] = []
    anio = None
    for elemento in BeautifulSoup(html or "", "html.parser").find_all(["p", "h2", "h3", "h4", "h5", "li"]):
        if elemento.name == "li":
            texto = re.sub(r"(?i)\s*:?\s*c[áa]tedra\s+[a-z]\b.*$", "", _texto(elemento))
            # (Nor one outside it: "PAFU ... opcional", "Informática (extracurricular)".)
            if anio and not re.search(r"(?i)optativ|electiv|opcional|extracurricular", texto):
                _agregar(materias, texto, anio)
            continue
        negrita = elemento if elemento.name != "p" else elemento.find(["b", "strong"])
        texto = _texto(negrita) if negrita else ""
        # A term's heading ("Primer Cuatrimestre") is inside the year.
        if texto and texto == _texto(elemento) and not re.search(r"(?i)cuatrimestre|semestre", texto):
            anio = anio_de(texto) if re.fullmatch(r"(?i)\w+\s+año", texto) else None
    return materias


def plan_titulo_y_lista(html: str) -> list[tuple[str, int]]:
    return desde_el_primero(_plan_titulo_y_lista(html))


_FIN_DEL_PLAN = re.compile(r"(?i)^(disposici[óo]n|resoluci[óo]n|res\.|requisitos|t[íi]tulo|modalidad|duraci[óo]n|"
                           r"inscrib|materias optativas|optativas|electivas|perfil|alcances|autorizad|plan de estudios? tentativo|"
                           r"ver correlatividades|plan de estudios?$)")


def _plan_texto_por_anio(html: str) -> list[tuple[str, int]]:
    """ESEADE: after "Plan de estudios", a line per year ("1º año") and a
    line per subject; a term's line ("Primer cuatrimestre") is not one. The
    plan ends at the first line that is not a subject: the ministry's
    disposition, the requirements, the degree."""
    soup = BeautifulSoup(html or "", "html.parser")
    for parte in soup.find_all(["script", "style", "nav", "header", "footer"]):
        parte.decompose()
    lineas = [clean_text(l) for l in soup.get_text("\n").split("\n") if clean_text(l)]
    inicio = next((i for i, l in enumerate(lineas) if l.lower().startswith("plan de estudio")), None)
    materias: list[tuple[str, int]] = []
    anio = None
    for linea in lineas[inicio + 1:] if inicio is not None else []:
        if re.fullmatch(r"(?i)\d+\s*[º°o]?\s*año|\w+\s+año", linea) and anio_de(linea):
            anio = anio_de(linea)
        elif re.search(r"(?i)cuatrimestre|semestre", linea) and len(linea.split()) <= 3:
            continue
        elif anio and _FIN_DEL_PLAN.match(linea):
            break
        elif anio:
            _agregar(materias, linea, anio)
    return materias


def plan_texto_por_anio(html: str) -> list[tuple[str, int]]:
    return desde_el_primero(_plan_texto_por_anio(html))


def _plan_kt_tabs(html: str) -> list[tuple[str, int]]:
    """UNaF, Recursos Naturales: a tab per year ("AÑO 1") and its content in
    the same order, the subjects listed under each term's heading."""
    soup = BeautifulSoup(html or "", "html.parser")
    titulos = [anio_de(_texto(t)) or (int(m.group(1)) if (m := re.search(r"(?i)año\s*(\d)", _texto(t))) else None)
               for t in soup.select("a.kt-tab-title")]
    contenidos = soup.select("div.kt-tab-inner-content")
    materias: list[tuple[str, int]] = []
    if len(titulos) != len(contenidos):
        return []
    for anio, contenido in zip(titulos, contenidos):
        for item in contenido.select("li") if anio else []:
            if not re.search(r"(?i)optativ|electiv", _texto(item)):
                _agregar(materias, _texto(item), anio)
    return materias


def plan_kt_tabs(html: str) -> list[tuple[str, int]]:
    return desde_el_primero(_plan_kt_tabs(html))


def _plan_obligatorias(html: str) -> list[tuple[str, int]]:
    """UNRC, Humanas: a table with a row per year ("Primer año") and a row
    per subject: its name, its term and its kind; only an OBLIGATORIA is
    the plan's (an optional language is one to choose)."""
    materias: list[tuple[str, int]] = []
    for tabla in BeautifulSoup(html or "", "html.parser").find_all("table"):
        anio = None
        for fila in tabla.find_all("tr"):
            celdas = [_texto(c) for c in fila.find_all(["td", "th"])]
            if len(celdas) == 1:
                anio = anio_de(celdas[0]) if re.fullmatch(r"(?i)\w+\s+año", celdas[0]) else None
            elif anio and len(celdas) >= 3 and celdas[-1].upper() == "OBLIGATORIA":
                _agregar(materias, celdas[0], anio)
        # A page with the new plan and the old one shows the new first.
        if materias:
            break
    return materias


def plan_obligatorias(html: str) -> list[tuple[str, int]]:
    return desde_el_primero(_plan_obligatorias(html))


def _plan_fadu(html: str) -> list[tuple[str, int]]:
    """UBA, FADU: a table per level under its heading, the CBC ("CICLO
    BÁSICO COMÚN", the career's first year) and "Nivel 1" to "Nivel 5"
    (its second year on); a subject's name after its code ("A1. Arquitectura
    I"). A row without a way to pass ("Matemática II On-line") is another
    way to take the one above."""
    materias: list[tuple[str, int]] = []
    for tabla in BeautifulSoup(html or "", "html.parser").find_all("table"):
        titulo = _texto(tabla.find_previous(["h2", "h3", "h4", "h5", "strong", "p"]))
        nivel = re.fullmatch(r"(?i)nivel\s+(\d)", titulo)
        anio = 1 if re.fullmatch(r"(?i)ciclo b[áa]sico com[úu]n", titulo) else (int(nivel.group(1)) + 1 if nivel else None)
        for fila in tabla.find_all("tr") if anio else []:
            celdas = [_texto(c) for c in fila.find_all(["td", "th"])]
            if len(celdas) < 3 or celdas[0].lower() == "materia" or not celdas[1]:
                continue
            # The CBC's "Intr. al ..." is a shortened word, not a code.
            nombre = re.sub(r"^Intr\.\s+", "Introducción ", celdas[0])
            nombre = re.sub(r"^[A-Z][A-Za-z0-9]{0,4}\.\s+", "", nombre)
            nombre = re.sub(r"\s*\(\*+\)$", "", nombre)
            if not re.search(r"(?i)optativ|electiv", nombre):
                _agregar(materias, nombre, anio)
    return materias


def plan_fadu(html: str) -> list[tuple[str, int]]:
    return desde_el_primero(_plan_fadu(html))
