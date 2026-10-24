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

import math
import re
import unicodedata
from collections import Counter
from html import unescape

from bs4 import BeautifulSoup, Tag

from rumbo_scraper.normalizers.text import clean_text, comparison_key

_ORDINALES = {"primer": 1, "primero": 1, "segundo": 2, "tercer": 3, "tercero": 3, "cuarto": 4,
              "quinto": 5, "sexto": 6}
_ANIO = re.compile(r"(?i)^\s*(primer|primero|segundo|tercer|tercero|cuarto|quinto|sexto)\s*(?:a[ñn]o)?\s*:?\s*$")
# "1° Año", "1er AÑO", "2do. Año", "1.er AÑO"
_ANIO_NUMERO = re.compile(r"(?i)^\s*(\d)\s*\.?\s*(?:er|ro|do|to|vo|mo|[°ºo])?\s*\.?\s*a[ñn]o\s*:?\s*$")
# Not subjects: an elective's slot, a heading that ends in a colon.
_NO_ES_MATERIA = re.compile(
    r"(?i)^(?:asignaturas?\s+|materias?\s+)?(?:optativas?|electivas?|seminario optativo)(?:\s+(?:[ivx]+|\d+|optativas?|electivas?))*$"
    r"|:$|^resoluci[óo]n(?!\s+de\s+(?:conflictos|problemas))|deber[áa]|^entre\s+\d|a determinar|^horas flexibles$"
    # A row's kind alone (Barceló's "Práctica", "Seminario", "Taller" column).
    r"|^(?:pr[áa]ctica|seminario|taller)$"
    # The plan's own data, not a subject: "TÍTULO DE PREGRADO: ...", "CARGA HORARIA TOTAL: ...".
    r"|^t[íi]tulo (?:de |intermedio|final)|^carga horaria|^duraci[óo]n\s*:"
    # A plan table's column heading (Morón: "Cod", "Asignatura", "Opción",
    # "Durac", "Correl" were published as subjects of 77 careers).
    r"|^(?:correl\w*|opci[oó]n|durac\w*|cod|c[oó]digo|asignatura|duraci[óo]ndelacarreraen)\.?$"
    # A term's or a duration's heading, hours, a total ("3º Cuatrimestre", "2 años
    # y medio", "120 horas", "Subtotal"); the staff of a diplomatura (UNTREF:
    # "Equipo", "Director", ": Mg. ..."); the office's hours (UNAHUR).
    r"|^\d+\s*[°º]?\s*cuatrimestre\.?$|^\d+\s+a[ñn]os(?:\s+y\s+medio)?\.?$|^(?:sub)?total$|^\d+\s+horas\.?$"
    r"|^(?:equipo|coordinador(?:a)?(?:\s+acad[ée]mico)?|docentes|director(?:a)?|comit[ée]\s+acad[ée]mico)$|^:\s"
    r"|^atenci[oó]n de lunes"
    # What the graduate will do, not a subject (UNICEN: "Realizar la programación, prueba...").
    r"|^[a-záéíóúñ]{4,}(?:ar|er|ir)\s+(?:el|la|los|las|un|una)\s\w+.*\s\w+\s\w+"
    # The page's asides (UCC's "Estamos en contacto" in 34 careers).
    r"|^estamos en contacto|^informaci[oó]n sobre la inscripci|^pre-?inscripci[oó]n|^\[?descargar|estar[áa]s en contacto|^examen de suficiencia"
    # An elective marked as such in UM's tables: "Sastrería(a)".
    r"|\(a\)$|derechos reservados")


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


_LIGADURAS = str.maketrans({"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "st", "ﬆ": "st"})


def _agregar(materias: list[tuple[str, int]], nombre: str, anio: int | None) -> None:
    # (A soft hyphen, "Seguridad" written "\u00adSeguridad", is not seen.)
    nombre = clean_text(nombre.replace("\u00ad", "")).replace("\xa0", " ").strip(" .;-–*")
    # A PDF's ligatures ("Planiﬁcación"): the letters they stand for.
    nombre = nombre.translate(_LIGADURAS)
    # A list's marks and codes: "› Nutrición" (UNAU), "COD: 101 - Guión" (UNMdP FAUD).
    nombre = re.sub(r"^(?:[›•·⏺◻▪■□◦\u2022\ufe0f\ufe0e]\s*)+", "", nombre)
    nombre = re.sub(r"(?i)^cod\.?:?\s*\d*\s*[-–]\s*", "", nombre)
    # Numbered in Roman figures: "VI.- Derecho del Trabajo I", "XI. Inglés I" (UEAN).
    nombre = re.sub(r"^[IVXL]{1,8}\s*\.-?\s*(?=[A-ZÁÉÍÓÚÑ])", "", nombre)
    # "Algebra I (anual)", "Rítmica (Cuatr.)", "Proyecto I Anual", "Matemática 1°C",
    # "(1° Cuatrimestre)", "(2do cuatrimestre)", "(Anual) Créditos 10.00": how long it runs, not its name.
    nombre = re.sub(r"(?i)\s*cr[ée]ditos\s*[\d.,]+\s*$", "", nombre)
    # "Optativa 1 (***)": the mark of a footnote.
    nombre = re.sub(r"\s*\(\*+\)\s*$", "", nombre)
    # "Redes y Comunicaciones (Sexto Semestre)": when it is taken.
    nombre = re.sub(r"(?i)\s*\((?:primer|segundo|tercer|cuarto|quinto|sexto|s[ée]ptimo|octavo|noveno|d[ée]cimo)\s+semestre\)\s*$", "", nombre)
    nombre = re.sub(r"(?i)\s*\(\s*(?:anual|cuatrimestral|semestral|cuatr\.?|\d\s*(?:[°º]|er|do|ro|to)?\s*(?:cuatr\.?|cuatrimestre|semestre|c))\s*\)\s*$", "", nombre)
    # A code before or after the name: "0401 Cálculo I" (UNRC Ingeniería), "Física I (00131)" (UNNOBA).
    nombre = re.sub(r"^\d{3,5}\s+(?=[A-ZÁÉÍÓÚÑ])", "", nombre)
    # Numbered in the list: "1 Introducción a la Arqueología" (UNT Naturales), "12. Estadística".
    nombre = re.sub(r"^\d{1,2}[.)-]?\s+(?=[A-ZÁÉÍÓÚÑ])", "", nombre)
    # "Biología General (D54)" (UNMdP Exactas): its code.
    nombre = re.sub(r"\s*\((?:[A-Z]{2})?\d{3,5}\)$|\s*\([A-Z]\d{2}\)$", "", nombre)
    # Its term as UM writes it: "Procesamiento de Imágenes (s2)", "(un semestre)".
    nombre = re.sub(r"(?i)\s*\((?:s\d|un semestre|anual)\)$", "", nombre)
    nombre = re.sub(r"(?i)\s+(?:anual|cuatrimestral|\d\s*[°º]\s*c)$", "", nombre)
    # (An acronym stays one: "TFG", "PPS".)
    if nombre.isupper() and len(nombre) > 5:
        from rumbo_scraper.parsers.guias_nacionales import con_tildes

        nombre = con_tildes(nombre)
    # "Anatomía Ii": the numeral of a subject's part is written in capitals.
    nombre = re.sub(r"(?i)\b(i{1,3}|iv|vi{0,3}|ix|x)\b(?=\s*$|\s*[:(-])", lambda m: m.group(1).upper(), nombre)
    # And of a part of that part: "ANALISIS MATEMATICO II A" (UdeMM) is
    # "Análisis Matemático II A", not "... Ii a".
    nombre = re.sub(r"(?i)\b(i{1,3}|iv|vi{0,3}|ix|x)\s+([a-d])$", lambda m: f"{m.group(1).upper()} {m.group(2).upper()}", nombre)
    nombre = re.sub(r"\s+", " ", nombre.replace("\u200b", "")).strip()
    if len(re.findall(r"[^\W\d_]", nombre)) < 3:
        return
    # A sentence ("El alumno debe aprobar 2 asignaturas electivas...") is a
    # rule of the plan, not a subject.
    # (A name runs to fifteen or sixteen words without a point or a comma:
    # ISALUD's "Teoría y técnica de Terapia Ocupacional en niños y
    # adolescentes con disfunciones motoras y sensoriales".)
    palabras = len(nombre.split())
    if palabras > 16 or (palabras > 14 and re.search(r"[.,;:]", nombre)) \
            or re.search(r"(?i)\bdebe\b|\bpromovido\b", nombre):
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
            columnas = fila.find_all(["td", "th"])
            celdas = [_texto(td) for td in columnas]
            celdas = [c for c in celdas if c] or [""]
            # A subject's row: its code and name, then its hours or, when the
            # hours cell is empty, its prerequisites ("3338 PRACTICAS Y
            # COMUNICACION EN FISICA | | 3022"). The cell also holds the
            # subject's notes ("... Para aprobar 1- Debe rendir la Prueba de
            # Suficiencia..."), and the name ends in the department's mark
            # ("MATEMATICA I C", "INTRODUCCION AL DERECHO C.A.").
            nombre_y_notas = re.split(r"\s+Para (?:aprobar|cursar|rendir)\b", celdas[0])[0]
            materia = _MATERIA_UNS.match(nombre_y_notas)
            if materia and len(columnas) > 1:
                # (A Roman numeral is the name's: "MATEMATICA I C" keeps the I.)
                nombre = re.sub(r"(?:\s+-)?\s+(?!(?:I{1,3}|IV|VI{0,3}|IX|X)$)[A-Z]{1,2}\.?(?:[A-Z]\.)?$", "",
                                materia.group(2).strip())
                # A requirement taken as an exam, not a subject ("PRUEBA DE SUFICIENCIA EN INGLES").
                if not re.match(r"(?i)prueba de suficiencia", nombre):
                    _agregar(materias, nombre, anio)
                continue
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
                    # Years starting over: each orientation's own years
                    # (Oceanografía's four), not one plan.
                    if materias and anio < max(a for _, a in materias if a):
                        return []
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
    # Where the right column starts varies by brochure (50 in Derecho's, 37
    # in Analista de Sistemas'): the column its bullets most often start at.
    from collections import Counter as _Counter
    comienzos = _Counter(m.start() for linea in (texto_con_columnas or "").splitlines()
                         for m in re.finditer(r"£", linea) if m.start() > 20)
    columna = min(_COLUMNA_UCSE, comienzos.most_common(1)[0][0]) if comienzos else _COLUMNA_UCSE
    for linea in (texto_con_columnas or "").splitlines():
        if "PLAN DE ESTUDIOS" in linea:
            dentro = True
            continue
        if not dentro:
            continue
        # The right column's text may start a character before its bullets:
        # what follows a wide gap after the left column's text is not its.
        izquierda = re.sub(r"(?<=\S)\s{4,}\S.*$", "", linea[:columna]).rstrip()
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


# UNNOBA's plans site (planesdeestudio.unnoba.edu.ar): a heading per year
# ("1º Año"), a button per subject (class "subject") with its code after it
# ("Física I (00131)"); an elective's possible subjects are in a <dialog>
# behind its button, and are not the plan's.
def plan_unnoba(html: str) -> list[tuple[str, int]]:
    materias: list[tuple[str, int]] = []
    anio = None
    for elemento in BeautifulSoup(html or "", "html.parser").find_all(True):
        if elemento.name in ("h1", "h2", "h3", "h4") and anio_de(_texto(elemento)):
            anio = anio_de(_texto(elemento))
        elif "subject" in (elemento.get("class") or []) and not elemento.find_parent("dialog") and anio:
            nombre = elemento.find("p")
            _agregar(materias, _texto(nombre or elemento), anio)
    return desde_el_primero(materias)


# A plan table whose header names its columns ("Código | Unidad curricular |
# Formato | Modalidad | ..."), a row per year across the whole table
# ("Primer año"), a row per subject (UNLa). The name is the column the header
# calls the subject's; a mark after it ("Sociología Política*") is a note.
_COLUMNA_DEL_NOMBRE = re.compile(r"(?i)^(unidad(es)? curricular(es)?|asignaturas?|materias?|espacios? curriculares?)$")


def plan_tabla_por_columna(html: str) -> list[tuple[str, int]]:
    materias: list[tuple[str, int]] = []
    for tabla in BeautifulSoup(html or "", "html.parser").find_all("table"):
        columna, anio = None, None
        for fila in tabla.find_all("tr"):
            celdas = [_texto(celda) for celda in fila.find_all(["td", "th"])]
            if columna is None:
                columna = next((i for i, c in enumerate(celdas) if _COLUMNA_DEL_NOMBRE.match(c)), None)
                continue
            if len(celdas) == 1 or (celdas and all(not c for c in celdas[1:])):
                # Another heading ("Otros requisitos") ends the year's rows.
                anio = anio_de(celdas[0])
                continue
            if anio and columna < len(celdas):
                _agregar(materias, celdas[columna].rstrip("*").strip(), anio)
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
_UCASAL_PERIODO = re.compile(r"^(?:ANUAL|\d\s*°\s*(?:SEM|CUAT)\.?|CUATRIM\.?)\s+")
# A brochure that lists electives in a column of their own ("PAISAJE I
# ... ELECTIVA") is a menu, and its lines run two names together.
_UCASAL_COLUMNA_ELECTIVA = re.compile(r"\S\s{3,}(?:ELECTIVA|OPTATIVA)\s*$")
# "PATOLOGÌA QUIRÙRGICA": accents Spanish does not write.
_UCASAL_ACENTO_GRAVE = re.compile(r"[ÀÈÌÒÙàèìòù]")
_UCASAL_FILA = re.compile(r"^\d{2}\s+\d{4}\s+(.+?)\s{2,}\d+\s+(?:\d\s*)?(?:Sem|Anual|ANUAL)")
_UCASAL_ABREVIADA = re.compile(r"[º°]|\w\.(?=\s*\w)|\w\.$")
_UCASAL_NO_ES = re.compile(r"(?i)^(prueba de suficiencia|plan de estudio|carrera|modalidad|plan\s+\d)|@|ucasal\.edu")


def plan_ucasal(texto_con_columnas: str) -> list[tuple[str, int]]:
    texto = texto_con_columnas or ""
    if "CORRELATIVIDADES DETALLADAS" in texto:
        return []
    if re.search(r"\bCód\.", texto) and "Régimen" in texto:
        return _ucasal_tabla_con_codigo(texto)
    if re.search(r"(?m)^\s*COD\s+ASIGNATURA\s+REGIMEN", texto):
        return _ucasal_anexo_con_codigo(texto)
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
    renglones: list[tuple[str, int]] = []
    encabezado = False
    for linea in texto.splitlines():
        if _UCASAL_COLUMNA_ELECTIVA.search(linea):
            return []
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
        if _UCASAL_ABREVIADA.search(nombre) or _UCASAL_ACENTO_GRAVE.search(nombre):
            return []
        if nombre.isupper():
            # (A footnote's number: "PRÁCTICA PROFESIONAL (1)".)
            renglones.append((re.sub(r"\s*\(\d\)$", "", nombre), anio))
    # Names cut at twenty letters leave none longer: a plan whose longest
    # name is twenty is taken for cut ("ESTADÍSTICA APLICADA" is whole in a
    # brochure that also prints longer ones).
    if renglones and max(len(nombre) for nombre, _ in renglones) == 20:
        return []
    from rumbo_scraper.parsers.guias_nacionales import con_tildes

    for nombre, anio in _ucasal_unir_partidos(renglones):
        # (Its short names in capitals too: "ÉTICA".)
        _agregar(materias, con_tildes(nombre), anio)
    return desde_el_primero(materias)


_UCASAL_REGIMEN = r"(?:Semestral|Anual|Cuatrimestral)\b"
_UCASAL_ORDINAL = {"PRIMER": 1, "SEGUNDO": 2, "TERCER": 3, "CUARTO": 4, "QUINTO": 5, "SEXTO": 6}


def _ucasal_tabla_con_codigo(texto: str) -> list[tuple[str, int]]:
    """The Jurídicas' plan sheets: a table per term ("Cód.", "MATERIA",
    "Régimen") under each year's heading ("PRIMER AÑO"). A name too long for
    its cell is wrapped around the row's code ("Negociación comercial,
    transcultural y" / "6   Semestral" / "relaciones humanas"). A code
    with no name in the text (one drawn as curves) leaves the plan unread."""
    materias: list[tuple[str, int]] = []
    anio = 0
    cabeza = ""        # a name's first line, before its code
    codigo = False     # a code read on a line of its own, its name not yet whole
    for linea in texto.splitlines():
        linea = linea.replace("\xa0", " ").strip()
        if not linea:
            continue
        if re.match(r"(?i)^seminarios\s+electivos", linea):
            break
        ordinal = re.fullmatch(r"(PRIMER|SEGUNDO|TERCER|CUARTO|QUINTO|SEXTO)\s+AÑO", linea)
        fila = re.match(rf"^(\d{{1,2}})\s+(\S.*?)\s+{_UCASAL_REGIMEN}", linea)
        solo_codigo = re.fullmatch(rf"\d{{1,2}}(?:\s+{_UCASAL_REGIMEN}.*)?", linea)
        if codigo and (ordinal or fila or solo_codigo or not cabeza):
            # (The name ended on its first line: "Teología I" over "14".)
            if not cabeza:
                return []
            _agregar(materias, cabeza, anio)
            cabeza, codigo = "", False
        if ordinal:
            anio, cabeza = _UCASAL_ORDINAL[ordinal.group(1)], ""
        elif fila and anio:
            _agregar(materias, fila.group(2), anio)
            cabeza = ""
        elif solo_codigo and anio:
            codigo = True
        elif re.match(rf"^-?\s*{_UCASAL_REGIMEN}", linea):
            continue
        else:
            nombre = re.split(rf"\s+-?\s*{_UCASAL_REGIMEN}|\s{{3,}}", linea)[0]
            # A heading, a total or the sheet's own title ("LICENCIATURA EN ...").
            if (not anio or nombre.isupper() or re.match(r"(?i)^(cód|materia|horas|total|carga|\d\S*\s+semestre|plan de|facultad)", nombre)
                    or not re.search(r"[a-záéíóúñ]", nombre)):
                cabeza, codigo = "", False
                continue
            if codigo:
                _agregar(materias, f"{cabeza} {nombre}", anio)
                cabeza, codigo = "", False
            else:
                cabeza = nombre
    if codigo:
        if not cabeza:
            return []
        _agregar(materias, cabeza, anio)
    return desde_el_primero(materias)


def _ucasal_anexo_con_codigo(texto: str) -> list[tuple[str, int]]:
    """The Ministry's annex of a plan ("COD", "ASIGNATURA", "REGIMEN"): a
    row per subject, its code and regime on the line in the middle of its
    name ("PSICOLOGÍA DEL" / "3  DESARROLLO Y DE LA  Anual" / "SUBJETIVIDAD").
    A name is centred on its code's line, as many of its lines above as
    below, which tells the tail of one name from the head of the next; a
    count that does not close leaves the plan unread."""
    from rumbo_scraper.parsers.guias_nacionales import con_tildes

    # The lines of the name column, each a row's code (or None) and its text.
    renglones: list[tuple[int | None, str]] = []
    anios: list[tuple[int, int]] = []   # (index of the first line after the heading, year)
    columna = 0
    for linea in texto.splitlines():
        linea = linea.replace("\xa0", " ")
        encabezado = re.match(r"^\s*COD\s+ASIGNATURA\s+", linea)
        if encabezado:
            columna = encabezado.end()
            continue
        if re.match(r"^\s*TÍTULO:", linea) and renglones:
            break
        ordinal = re.fullmatch(r"\s*(PRIMER|SEGUNDO|TERCER|CUARTO|QUINTO|SEXTO)\s+AÑO\s*", linea)
        if ordinal:
            anios.append((len(renglones), _UCASAL_ORDINAL[ordinal.group(1)]))
            continue
        if not columna or not anios:
            continue
        fila = re.match(rf"^\s*(\d{{1,2}})\s+(.*?)\s*{_UCASAL_REGIMEN}", linea)
        if fila:
            renglones.append((int(fila.group(1)), fila.group(2)))
            continue
        nombre = linea[:columna].strip()
        # (The table's heading over two lines, a total, the page's foot.)
        if nombre and re.search(r"[A-ZÁÉÍÓÚÑ]", nombre) and not re.search(r"\d|CARGA|SEMANAL|DNGU|Página", nombre) \
                and not linea[columna:].strip().startswith(("HORARIA", "TOTAL", "DICTADO")):
            renglones.append((None, nombre))
    codigos = [i for i, (codigo, _) in enumerate(renglones) if codigo is not None]
    if not codigos or [renglones[i][0] for i in codigos] != list(range(1, len(codigos) + 1)):
        return []
    materias: list[tuple[str, int]] = []
    inicio = 0          # where the current name starts
    for n, i in enumerate(codigos):
        cabeza = i - inicio
        fin = i + 1 + cabeza
        siguiente = codigos[n + 1] if n + 1 < len(codigos) else len(renglones)
        if fin > siguiente or any(renglones[j][0] is not None for j in range(inicio, fin) if j != i):
            return []
        # (A year's heading falls between two names, never inside one.)
        if any(inicio < a < fin for a, _ in anios):
            return []
        anio = max((a for a in anios if a[0] <= i), default=(0, 0))[1]
        _agregar(materias, con_tildes(" ".join(t for _, t in renglones[inicio:fin] if t)), anio)
        inicio = fin
    if inicio != len(renglones):
        return []
    return desde_el_primero(materias)


_UCASAL_NUMERAL = re.compile(r"\s+(?:I{1,3}|IV|VI{0,3}|IX|X)$")


def _ucasal_unir_partidos(renglones: list[tuple[str, int]]) -> list[tuple[str, int]]:
    """A name the brochure wraps onto a second line, joined: where the first
    ends in a comma or a word that does not end a name ("... ENERGÉTICA PARA"
    over "DISTINTOS TIPOS DE ..."), or where the two make the next of a
    series the plan has ("ADMINISTRACIÓN" over "FINANCIERA II", with
    "ADMINISTRACIÓN FINANCIERA I")."""
    series = Counter(_UCASAL_NUMERAL.sub("", nombre) for nombre, _ in renglones
                     if _UCASAL_NUMERAL.search(nombre))
    unidos: list[tuple[str, int]] = []
    i = 0
    while i < len(renglones):
        nombre, anio = renglones[i]
        if i + 1 < len(renglones):
            cola, anio_cola = renglones[i + 1]
            junto = f"{nombre} {cola}"
            sigue = bool(re.search(r",$|\s(?:DE|DEL|LA|LAS|LOS|EL|Y|E|EN|A|AL|CON|PARA|POR)$", nombre))
            if anio_cola == anio and (sigue or (len(cola.split()) <= 3 and _UCASAL_NUMERAL.search(cola)
                                                and series[_UCASAL_NUMERAL.sub("", junto)])):
                unidos.append((junto, anio))
                i += 2
                continue
        unidos.append((nombre, anio))
        i += 1
    return unidos


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
        if re.match(r"(?i)^([12]\s*[º°]|primer|segundo)\s*cuatrimestre", linea) or _LEYENDA.match(linea):
            continue
        if anio and (len(linea) > 90 or re.match(
                r"(?i)^(requisitos|inscrip|documentaci|informaci|condiciones|t[íi]tulo|alcances|perfil|"
                r"materias optativas|optativas|asignaturas optativas|preinscrip|¿|para finalizar la carrera|"
                r"espacios de talleres|descarg|quiero recibir|aclaraciones$|ingreso \d{4}$|autoridades$|¡?quiero inscribirme)", linea)):
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
    for elemento in (titulo.find_all_next(["h2", "h3", "h4", "h5", "h6", "strong", "li"]) if titulo else []):
        texto = _texto(elemento)
        # The electives' pool ("Asignaturas optativas") and, past the plan,
        # each campus's address and mail under an h3 ("La Plata").
        if elemento.name in ("h2", "h3") or (elemento.name == "strong" and re.match(r"(?i)asignaturas optativas|optativas$", texto)):
            break
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


def plan_isalud(html: str) -> list[tuple[str, int]]:
    """ISALUD's plan pages (/pregrado-y-grado/plan-de-estudios/<career>):
    under "PLAN DE ESTUDIOS", a heading per year ("Primer año") and a
    paragraph per subject. A year split into options ("OPCIÓN A: ÁREA DE
    NUTRICIÓN CLÍNICA") is a choice, and a plan without it would read one
    year short: none. The complementary subjects, of no year, end it."""
    soup = BeautifulSoup(html or "", "html.parser")
    # (Since 2026 the heading is a bold paragraph, "PLAN DE ESTUDIO".)
    titulo = soup.find(lambda e: (e.name in ("h2", "h3") or (e.name == "p" and e.find(["strong", "b"])))
                       and re.match(r"(?i)plan de estudios?$", _texto(e)))
    materias: list[tuple[str, int]] = []
    anio = None
    for elemento in titulo.find_all_next(["h2", "h3", "h4", "p"]) if titulo else []:
        texto = _texto(elemento)
        if not texto:
            continue
        if re.match(r"(?i)opci[óo]n\b", texto):
            return []
        # The next heading (the degree, "Título: ...") or the page's form end it.
        if (elemento.name in ("h2", "h3") and materias) or re.match(
                r"(?i)asignaturas complementarias|dejanos tu consulta|los alumnos que|requisitos? de egreso", texto):
            break
        # A year: a heading ("Primer año") or a paragraph of it in bold.
        negrita = elemento.find(["strong", "b"])
        if elemento.name == "h4" or (negrita and _texto(negrita) == texto):
            anio = anio_de(texto) or (anio if elemento.name != "h4" else None)
            continue
        if anio:
            _agregar(materias, texto, anio)
    return desde_el_primero(materias)


_MATERIA_IUPFA = re.compile(r"^\s*(\d{1,2})\s+(\S.*?)\s{2,}((?:ANUAL|CUATRIMESTRAL|SEMESTRAL|BIMESTRAL|A DISTANCIA|"
                            r"PRESENCIAL|\d{1,3})\b.*)$")
_TOTAL_ANIO_IUPFA = re.compile(r"(?i)(?:total\s+(?:de\s+)?horas|carga\s+horaria)\s+(?:del\s+)?"
                               r"(primer|segundo|tercer|cuarto|quinto)\s+a[ñn]o\s*:?\s*([\d.]+)")


def plan_iupfa(texto_con_columnas: str) -> list[tuple[str, int]]:
    """The Federal Police university's plans (``pdftotext -layout``): a
    heading per year ("PRIMER AÑO"), a row per subject with its code, name
    and term or hours ("01  BALÍSTICA I  ANUAL  128", "7  INFORMÁTICA II
    64  PRESENCIAL  1"). The codes run from 1 without a gap, and where the
    plan states a year's hours ("Total horas primer año: 560 horas") the
    year's rows (each its largest figure) add up to them."""
    materias: list[tuple[str, int]] = []
    anio = None
    codigos: list[int] = []
    horas: dict[int, float] = {}
    for linea in texto_con_columnas.splitlines():
        encabezado = _ANIO_IUCBC.match(linea)
        if encabezado:
            anio = _ORDINALES_UHIBA[encabezado.group(1).lower()]
            continue
        materia = _MATERIA_IUPFA.match(linea)
        if anio and materia:
            codigos.append(int(materia.group(1)))
            cifras = [int(c) for c in re.findall(r"\b\d{1,3}\b", materia.group(3))]
            horas[anio] = horas.get(anio, 0) + (max(cifras) if cifras else 0)
            _agregar(materias, materia.group(2), anio)
    # (A row the columns moved may come out of order: "6 7 8 4 5".)
    if sorted(codigos) != list(range(1, len(codigos) + 1)):
        return []
    for ordinal, declarado in _TOTAL_ANIO_IUPFA.findall(texto_con_columnas):
        if horas.get(_ORDINALES_UHIBA[ordinal.lower()], 0) != int(declarado.replace(".", "")):
            return []
    # Rows the reader missed show in a second part without its first
    # ("Enfermería Materno Infantil II", no "... I"): not the whole plan.
    # (The first part may be written a little differently: "Estudio de las Vías de
    # Circulación I" and "Estudios ... II".)
    from difflib import SequenceMatcher

    primeras = [comparison_key(n[:-2]) for n, _ in materias if re.search(r"\sI$", n)]
    for nombre, _ in materias:
        if re.search(r"\sII$", nombre) and not any(
                SequenceMatcher(None, comparison_key(nombre[:-3]), p).ratio() >= 0.8 for p in primeras):
            return []
    return desde_el_primero(materias)


_SEMESTRE_ING_UNLP = re.compile(r"^\s*(\d{1,2})\s*[º°]\s*Semestre\s*$")
_MATERIA_ING_UNLP = re.compile(r"^\s{0,4}([A-Z]\d{4})\s+(\S.*?)\s{2,}(?:[A-Z]{2}(?:/[A-Z]{2})?)\s")


def plan_ing_unlp(texto_con_columnas: str) -> list[tuple[str, int]]:
    """UNLP Ingeniería's plans (``plan.php?carrera=...``, a PDF its system
    prints): a heading per term ("3º Semestre"), a row per subject with its
    code, name and kind ("F1304  Matemática C  CB  9  144"), a long name
    going on below in the name's column ("... y Analisis" / "Numérico").
    The year is the term's pair. The levelling course before the first term
    and the complementary activities ("AFC 1") are not subjects."""
    materias: list[list] = []
    semestre, ultima = None, None
    for linea in texto_con_columnas.splitlines():
        # (The plan's terms end where its language requirement, practice
        # hours and optional subjects begin; "Ver al dorso" is a page's foot.)
        if re.match(r"^\s*(Idioma|OPTATIVAS|Formaci[óo]n Pr[áa]ctica)\b", linea):
            break
        if re.match(r"(?i)\s*ver al dorso", linea):
            ultima = None
            continue
        encabezado = _SEMESTRE_ING_UNLP.match(linea)
        if encabezado:
            semestre, ultima = int(encabezado.group(1)), None
            continue
        if re.match(r"^\s*Nivelaci[óo]n\s*$", linea):
            semestre, ultima = None, None
            continue
        materia = _MATERIA_ING_UNLP.match(linea)
        if materia and semestre:
            ultima = [materia.group(2), (semestre + 1) // 2]
            materias.append(ultima)
            continue
        # A wrapped name: text alone, in the name's column.
        seguida = re.match(r"^\s{8,24}(\S.*?)(?:\s{3,}.*)?$", linea)
        if ultima and seguida and not re.search(r"\d{4}", seguida.group(1)):
            ultima[0] += " " + seguida.group(1)
        elif linea.strip():
            ultima = None
    plan: list[tuple[str, int]] = []
    for nombre, anio in materias:
        _agregar(plan, re.sub(r"\s*\(1/2 semestre\)", "", nombre), anio)
    return desde_el_primero(plan)


def plan_filo_unt(cajas: str) -> list[tuple[str, int]]:
    """UNT Filosofía y Letras' brochures: the plan a table with a column per
    year ("1° año" ... "5° año"), each cell a block of text in ``pdftotext
    -bbox-layout`` (a name wrapped over lines is one block). A cell goes to
    the column its left edge is under; the table ends at its foot ("Carga
    horaria total"). "Área de Formación General" is a slot, not a subject."""
    bloques = []
    for x, y, contenido in re.findall(r'<block xMin="([\d.]+)" yMin="([\d.]+)"[^>]*>(.*?)</block>', cajas or "", re.S):
        texto = clean_text(" ".join(re.findall(r">([^<]+)</word>", contenido)))
        bloques.append((float(x), float(y), texto))
    columnas = {}
    for x, y, texto in bloques:
        anio = re.fullmatch(r"(\d)\s*[°º]\s*año", texto, re.I)
        if anio:
            columnas[int(anio.group(1))] = (x, y)
    if not columnas or len({round(y) for x, y in columnas.values()}) != 1:
        return []
    arriba = next(iter(columnas.values()))[1]
    materias: list[tuple[str, int]] = []
    for x, y, texto in sorted(bloques, key=lambda b: (b[1], b[0])):
        if y <= arriba:
            continue
        if re.search(r"(?i)carga horaria total|alcances del t[íi]tulo", texto):
            break
        anio = next((a for a, (cx, _) in columnas.items() if abs(cx - x) < 6), None)
        if anio and not re.fullmatch(r"(?i)área de formación general", texto):
            _agregar(materias, texto, anio)
    return desde_el_primero(sorted(materias, key=lambda m: m[1]))


plan_filo_unt.cajas = True


def plan_uflo(html: str) -> list[tuple[str, int]]:
    """UFLO's career pages: "Plan de estudios" in tabs (a Gutena tabs
    block), a tab per year ("Primer Año") holding its subjects as lists.
    Tabs that are not a year ("Espacios Optativos", "Otros Requisitos")
    are left out, and so are the lists under an orientation
    ("·Orientación en Tecnología Educativa"): a student takes one."""
    soup = BeautifulSoup(html or "", "html.parser")
    materias: list[tuple[str, int]] = []
    for bloque in soup.select(".gutena-tabs-block"):
        anios = {t.get("data-tab"): anio_de(_texto(t)) for t in bloque.select(".gutena-tab-title")}
        for panel in bloque.select(".gutena-tab-block"):
            anio = anios.get(panel.get("data-tab"))
            if not anio:
                continue
            alternativa = False
            for parte in panel.find_all(["p", "ul"], recursive=False):
                if parte.name == "p":
                    alternativa = bool(re.match(r"(?i)^[·•\s]*orientaci[oó]n", _texto(parte))) or (
                        alternativa and not _texto(parte))
                    continue
                if not alternativa:
                    for item in parte.find_all("li"):
                        _agregar(materias, _texto(item).rstrip("*"), anio)
    return desde_el_primero(materias)


def plan_um(html: str) -> list[tuple[str, int]]:
    """Morón's career pages since its new site: "PLAN DE ESTUDIO", a
    ``<details>`` per year ("Primer Año") holding a table, a subject a row
    (``td[rel=desc]``, in capitals). The sections that are not a year (the
    electives' pool, "ASIG.OPTATIV.") are left out, and so are the rows a
    year marks as one option among several ("Opt.A")."""
    materias: list[tuple[str, int]] = []
    for seccion in BeautifulSoup(html or "", "html.parser").find_all("details"):
        resumen = seccion.find("summary")
        anio = anio_de(_texto(resumen)) if resumen and len(_texto(resumen)) < 20 else None
        if not anio:
            continue
        for fila in seccion.find_all("tr"):
            nombre, opcion = fila.find("td", rel="desc"), fila.find("td", rel="opcion")
            if nombre and _texto(nombre) and not (opcion and _texto(opcion)):
                _agregar(materias, _texto(nombre), anio)
    return desde_el_primero(materias)


def plan_ubp(html: str) -> list[tuple[str, int]]:
    """Blas Pascal's career pages: the plan in ``section#plan``, an accordion
    with a card per year ("PRIMER AÑO"), its subjects one per line under
    each term ("1º Cuatrimestre"), most marked ">" (Relaciones Públicas'
    sixth term is not)."""
    seccion = BeautifulSoup(html or "", "html.parser").find("section", id="plan")
    if not seccion:
        return []
    materias: list[tuple[str, int]] = []
    for tarjeta in seccion.select(".card"):
        anio = anio_de(_texto(tarjeta.select_one(".card-header")))
        cuerpo = tarjeta.select_one(".card-body")
        if not anio or not cuerpo:
            continue
        en_un_termino = False
        for linea in cuerpo.get_text("\n").splitlines():
            linea = clean_text(linea).replace("\xa0", " ").strip()
            if re.match(r"(?i)^\d+\s*[º°]?\s*(cuatrimestre|semestre)$", linea):
                en_un_termino = True
            elif linea.startswith(">") or (en_un_termino and re.search(r"[A-Za-zÁÉÍÓÚáéíóúñÑ]{3}", linea)):
                # (Psicología marks how each is taken: "Psicoanálisis (D)", "Psicopatología | (D)".)
                _agregar(materias, re.sub(r"\s*\|?\s*\([DP]\)\s*$", "", linea.lstrip("> ")), anio)
    return desde_el_primero(materias)


def _renglones(cajas: str) -> list[tuple[int, float, float, str]]:
    """The lines of ``pdftotext -bbox-layout``: (page, left edge, top, text)."""
    renglones = []
    for pagina, contenido in enumerate(re.findall(r"<page\b.*?</page>", cajas or "", re.S)):
        for x, y, linea in re.findall(r'<line xMin="([\d.]+)" yMin="([\d.]+)"[^>]*>(.*?)</line>', contenido, re.S):
            texto = clean_text(" ".join(re.findall(r">([^<]+)</word>", linea)))
            if texto:
                renglones.append((pagina, float(x), float(y), texto))
    return renglones


def plan_iuce(cajas: str) -> list[tuple[str, int]]:
    """The IUCE's career brochures (Mendoza): the plan a column per year
    ("1° Año" ... "4° Año"), each subject marked "॰" and wrapped over lines
    ("॰Marco legal" / "de las organizaciones"). A line goes to the column its
    left edge is under the mark of; "Talleres de aplicación ágil:" heads the
    workshops that follow, which are subjects too. "Tecnicatura Universitaria",
    between the columns, marks the intermediate degree."""
    renglones = _renglones(cajas)
    columnas = {}
    for pagina, x, y, texto in renglones:
        anio = re.fullmatch(r"(\d)\s*[°º]\s*Año", texto)
        if anio:
            columnas[int(anio.group(1))] = (pagina, x, y)
    if not columnas or len({(p, round(y)) for p, _, y in columnas.values()}) != 1:
        return []
    pagina, _, arriba = next(iter(columnas.values()))
    materias: list[list] = []
    for anio, (_, cx, _) in sorted(columnas.items()):
        bajo = sorted((y, x, t) for p, x, y, t in renglones if p == pagina and y > arriba)
        marca = next((x for y, x, t in bajo if t.startswith("॰") and 0 < x - cx < 40), None)
        if marca is None:
            return []
        ultima, abajo = None, arriba
        for y, x, texto in bajo:
            if abs(x - marca) > 3:
                continue
            # The column ends where its list does (the brochure's icons and addresses below).
            if y - abajo > 45:
                break
            abajo = y
            # Logística's brochure marks one subject twice: "॰Transporte" / "॰Terrestre y en FFRR".
            if texto.startswith("॰") and not (ultima and ultima[0] == "Transporte" and texto.startswith("॰Terrestre")):
                ultima = [texto.lstrip("॰ "), anio]
                materias.append(ultima)
            elif texto.startswith("॰"):
                ultima[0] += " " + texto.lstrip("॰ ")
            elif re.fullmatch(r"(?i)talleres de aplicaci[oó]n [aá]gil:?", texto):
                ultima = None
            elif ultima:
                ultima[0] += " " + texto
            else:
                return []
    plan: list[tuple[str, int]] = []
    for nombre, anio in materias:
        _agregar(plan, nombre, anio)
    return desde_el_primero(plan)


plan_iuce.cajas = True


def plan_iuas(cajas: str) -> list[tuple[str, int]]:
    """The IUAS's career brochures (Mendoza): "Primer año" or "1er Año"...
    each followed by its subjects, one per line and marked "*" or "•". Some pages
    print every word twice, the copy a little to the right: a word with its
    twin to its left on the same line is the copy."""
    palabras = []
    for pagina, contenido in enumerate(re.findall(r"<page\b.*?</page>", cajas or "", re.S)):
        for x, y, texto in re.findall(r'<word xMin="([\d.]+)" yMin="([\d.]+)"[^>]*>([^<]+)</word>', contenido):
            palabras.append((pagina, round(float(y), 1), float(x), texto))
    copias = {(p, y, round(x), t) for p, y, x, t in palabras}
    lineas: dict[tuple[int, float], list[tuple[float, str]]] = {}
    for p, y, x, t in palabras:
        if not any((p, y, round(x) - d, t) in copias for d in (17, 18, 19)):
            lineas.setdefault((p, y), []).append((x, t))
    materias: list[list] = []
    anio, ultima = None, None
    for clave in sorted(lineas):
        texto = clean_text(" ".join(t for _, t in sorted(lineas[clave])))
        if len(texto) < 15 and re.search(r"(?i)\baño$", texto) and anio_de(texto):
            anio, ultima = anio_de(texto), None
        # Marked "*", "•" (or, once, "¨").
        elif anio and texto[:1] in "*•¨":
            ultima = [texto.lstrip("*•¨ "), anio]
            materias.append(ultima)
        # A name wrapped after a word that cannot end it ("... Sistemas de Agua y el" / "Saneamiento").
        elif ultima and re.search(r"(?i)\s(?:de|del|la|las|el|los|y|e|en|a|para)$", ultima[0]):
            ultima[0] += " " + texto
        else:
            anio, ultima = None, None
    plan: list[tuple[str, int]] = []
    for nombre, anio in materias:
        _agregar(plan, nombre, anio)
    return desde_el_primero(plan)


plan_iuas.cajas = True


def plan_iuymca(cajas: str) -> list[tuple[str, int]]:
    """The YMCA university's career sheets (PDFs on Drive): "Plan de
    estudio", a column per year, its subjects numbered through the whole
    plan ("1. Anatomía", "14. Natación y su didáctica", "01 - Teoría e
    Historia...") and wrapped over lines. The numbered lines' left edges
    make the columns, left to right the years; a line without a number
    continues the one above it in its column. The table ends at the
    electives ("Espacios curriculares a cursar...") or the entry
    requirements. The numbers must run on with no gap from the first year
    to the last, or it is not read."""
    renglones = _renglones(cajas)
    inicio = next(((p, y) for p, x, y, t in renglones if re.fullmatch(r"(?i)plan de estudios?", t)), None)
    if not inicio:
        return []
    pagina, arriba = inicio
    fin = min((y for p, x, y, t in renglones if p == pagina and y > arriba
               and re.match(r"(?i)(espacios curriculares|requisitos de ingreso|talleres)", t)), default=1e9)
    tabla = sorted((y, x, t) for p, x, y, t in renglones if p == pagina and arriba < y < fin)
    numerados = [(y, x, t) for y, x, t in tabla if re.match(r"\d{1,2}\s*(?:\.|-)\s+\S", t)]
    columnas: list[list[float]] = []
    for x in sorted(x for _, x, _ in numerados):
        if columnas and x - columnas[-1][-1] < 50:
            columnas[-1].append(x)
        else:
            columnas.append([x])
    if not 2 <= len(columnas) <= 6:
        return []
    bordes = [(min(c) - 15, max(c) + 15) for c in columnas]
    por_columna: list[list[list]] = [[] for _ in columnas]
    for y, x, texto in tabla:
        anio = next((i for i, (a, b) in enumerate(bordes) if a <= x <= b), None)
        if anio is None:
            continue
        numero = re.match(r"(\d{1,2})\s*(?:\.|-)\s+(\S.*)", texto)
        if numero:
            por_columna[anio].append([int(numero.group(1)), numero.group(2)])
        elif por_columna[anio]:
            por_columna[anio][-1][1] += " " + texto
    numeros = [n for columna in por_columna for n, _ in columna]
    if not numeros or numeros != list(range(numeros[0], numeros[0] + len(numeros))):
        return []
    plan: list[tuple[str, int]] = []
    for anio, columna in enumerate(por_columna, 1):
        for _, nombre in columna:
            _agregar(plan, nombre, anio)
    return desde_el_primero(plan)


plan_iuymca.cajas = True
# Its sheets are on Drive, with other sites' documents: what it does not read goes to the general reader.
plan_iuymca.respaldo = True


def plan_fcnym(html: str) -> list[tuple[str, int]]:
    """UNLP Naturales' plan pages: a table per year headed "Nº | Materia |
    Duración | ...", the year in bold just before it ("Primer Año"). A row
    is a subject when it has its number; the language test's table has
    none, and an orientation's ("27-A0") is not every student's."""
    soup = BeautifulSoup(html or "", "html.parser")
    # A former plan ("... ingreso anterior a 2019") is not the career's.
    if re.search(r"(?i)anterior a \d{4}|plan anterior", _texto(soup.title) + " " + _texto(soup.find("h1"))):
        return []
    materias: list[tuple[str, int]] = []
    for tabla in soup.find_all("table"):
        filas = tabla.find_all("tr")
        encabezado = [_texto(c).lower() for c in filas[0].find_all(["th", "td"])] if filas else []
        if "materia" not in encabezado:
            continue
        columna = encabezado.index("materia")
        titulo = tabla.find_previous(lambda e: e.name in ("strong", "b", "h2", "h3", "h4", "h5") and anio_de(_texto(e)))
        anio = anio_de(_texto(titulo)) if titulo else None
        # (The heading must be this table's, not an earlier one's.)
        if not anio or (titulo.find_next("table") is not tabla):
            continue
        for fila in filas[1:]:
            celdas = [_texto(c) for c in fila.find_all(["td", "th"])]
            # ("27-A0": an orientation's subject, not every student's.)
            if len(celdas) > columna and re.fullmatch(r"\d{1,2}", celdas[0]) and celdas[columna]:
                _agregar(materias, celdas[columna], anio)
    return desde_el_primero(materias)


_ANIO_DNGU = re.compile(r"^\s*(PRIMER|SEGUNDO|TERCER|CUARTO|QUINTO|SEXTO)\s+AÑO\b")
# (UADER's Economics plans head each year "1º Año".)
_ANIO_NUMERO_DNGU = re.compile(r"^\s*([1-6])\s*[º°]\s*Año\s*$")
# ("---" where a row has no term: UNRN's "38 Trabajo Final Integrador --- 0 128".)
_REGIMEN_DNGU = r"(?:Cuatrimestral|Anual|ANUAL|Semestral|Bimestral|Trimestral|C[12](?=\s)|-{3}(?=\s))"
# (UNSAdA numbers its subjects with four digits: "0279"; UADER's Economics with six: "205101".)
_FILA_DNGU = re.compile(r"^\s{0,3}(\d{1,4}(?:\.\d{1,2}){0,3}\.?|\d{6})\s+(.*?)\s*" + _REGIMEN_DNGU + r"(?:\b|\s)")
_NO_ES_NOMBRE_DNGU = re.compile(r"(?i)^(C[OÓ]D|CARGA|SEMANAL|HORARIA|TOTAL$|MODALIDAD|DICTADO|T[ÍI]TULO|IF-\d|P[áa]gina|"
                                r"Digitally|Date:|Anexo|N[úu]mero:|Referencia)")


def plan_dngu(texto_con_columnas: str) -> list[tuple[str, int]]:
    """The plan in a Ministry resolution's annex (DNGU's table: "COD
    ASIGNATURA REGIMEN CARGA HORARIA ..."), ``pdftotext -layout``: a
    heading per term ("PRIMER AÑO-PRIMER CUATRIMESTRE") and a numbered row
    per subject. The cell centres its name, so a name over two lines has
    one above its number's row and one below ("Introducción a la" / "1
    Cuatrimestral 6 90" / "Computación"). A row with its name empty takes
    the loose line above and the one below; loose lines that cannot be
    told to one row or the next leave no plan."""
    lineas = texto_con_columnas.splitlines()
    if "ASIGNATURA" not in texto_con_columnas.upper() or not any(
            _ANIO_DNGU.match(l) or _ANIO_NUMERO_DNGU.match(l) for l in lineas):
        return []
    filas: list[dict] = []
    sueltas: list[str] = []
    anio = None
    for linea in texto_con_columnas.splitlines():
        if not linea.strip():
            continue
        encabezado = _ANIO_DNGU.match(linea)
        if encabezado:
            anio, sueltas = _ORDINALES_UHIBA[encabezado.group(1).lower()], []
            continue
        encabezado = _ANIO_NUMERO_DNGU.match(linea)
        if encabezado:
            anio, sueltas = int(encabezado.group(1)), []
            continue
        if re.match(r"^\s*T[ÍI]TULO:", linea) and filas:
            break
        fila = _FILA_DNGU.match(linea)
        if fila and anio:
            filas.append({"anio": anio, "nombre": clean_text(fila.group(2)), "antes": list(sueltas), "despues": []})
            sueltas = []
            continue
        # A loose line far to the right is another column's (UNRN's
        # correlatives, "Curso nivelatorio-" / "1"), not a name's; and a
        # name's piece keeps only what comes before the next column
        # (UADER's "Estructura y Política      213-318-").
        if len(linea) - len(linea.lstrip()) > 45:
            continue
        texto = clean_text(re.split(r"\s{3,}", linea.strip())[0])
        if anio and texto and not _NO_ES_NOMBRE_DNGU.match(texto) and not re.search(r"\d{2,}", texto):
            # In lower case, or a part's numeral alone ("I"), it goes on from
            # the row above ("Infraestructura para Ciencia" / "de Datos").
            ultimo = " ".join([filas[-1]["nombre"]] + filas[-1]["despues"]).strip() if filas else ""
            if filas and not sueltas and (texto[:1].islower() or re.fullmatch(r"[IVX]{1,4}", texto) or re.search(
                    r"(?i)\b(de|del|la|las|los|el|y|e|en|para|a|al|con|por)$", ultimo)):
                filas[-1]["despues"].append(texto)
                continue
            sueltas.append(texto)
            # A loose line right under a row without its name is that row's.
            if filas and not filas[-1]["nombre"] and not filas[-1]["despues"] and len(sueltas) == 1:
                previa = filas[-1]
                if previa["antes"]:
                    previa["despues"].append(sueltas.pop())
    materias: list[tuple[str, int]] = []
    for fila in filas:
        partes = fila["antes"] + ([fila["nombre"]] if fila["nombre"] else []) + fila["despues"]
        # A named row with loose lines above (unless they end on a word that
        # goes on: "Producción de Textos para la"), or a row with no name at
        # all: unclear.
        conectan = all(re.search(r"(?i)\b(de|del|la|las|los|el|y|e|en|para|a|al|con|por)$", a) for a in fila["antes"])
        # (Or a line above and one below: a name centred over three lines,
        # "Prácticas en Nutrición" / "Clínica y Administración de" / "Servicios Alimentarios".)
        centrada = len(fila["antes"]) == 1 and len(fila["despues"]) == 1
        if (fila["nombre"] and fila["antes"] and not (conectan or centrada)) or not partes or len(fila["antes"]) > 2:
            return []
        _agregar(materias, " ".join(partes), fila["anio"])
    return desde_el_primero(materias)


def plan_fcf_unam(html: str) -> list[tuple[str, int]]:
    """UNaM Forestales: a table whose rows go in pairs, the years' titles
    ("PRIMER AÑO", "SEGUNDO AÑO") over a cell per year, its subjects a list
    ("Física I (A)", "(C) Dibujo Técnico (C)"): the term's mark, "(A)"
    yearly or "(C)" by term, is not the name."""
    tabla = BeautifulSoup(html or "", "html.parser").find("table")
    materias: list[tuple[str, int]] = []
    anios: list[int | None] = []
    for fila in tabla.find_all("tr") if tabla else []:
        celdas = fila.find_all(["td", "th"])
        titulos = [anio_de(_texto(c)) for c in celdas]
        if any(titulos) and not fila.find("li"):
            anios = titulos
            continue
        for anio, celda in zip(anios, celdas):
            for item in celda.find_all("li") if anio else []:
                nombre = re.sub(r"^\((?:A|C)\)\s*|\s*\((?:A|C)\)$", "", _texto(item)).strip(" .")
                # (The introductory module is the entrance course, not a subject.)
                if nombre and not re.match(r"(?i)m[óo]dulo introductorio", nombre):
                    _agregar(materias, nombre, anio)
        anios = []
    return desde_el_primero(sorted(materias, key=lambda m: m[1]))


_ANIO_DISENO = re.compile(r"(?i)^(primer|segundo|tercer|cuarto|quinto)\s+a[ñn]o\b(?!\s+de\b)")
_REGIMEN_DISENO = re.compile(r"(?i)^(anual|cuat(?:rim)?\.?|cuatrimestral|1er\.? cuat\.?|2do\.? cuat\.?)$")
_NO_ES_UNIDAD = re.compile(r"(?i)^(unidad curricular|campo de la|total\b|r[ée]gi|formato|carga|m[óo]d\.|ch\b|\d|dise[ñn]o curricular$)")


def plan_diseno_pba(cajas: str) -> list[tuple[str, int]]:
    """A curricular design of the Province of Buenos Aires (``pdftotext
    -bbox-layout``): its "Estructura curricular" a table per year ("Primer
    año"), a row per unit with its name, its term ("Anual", "Cuat."), its
    format and hours. Each cell is a block of text, a name over two lines
    one block ("Educación y transformaciones sociales contemporáneas"). A
    unit is a block of the name's column with a term's block at its height;
    the year, the table's heading above it on the page. The page's prose
    has no term beside it."""
    materias: list[tuple[str, int]] = []
    anio, crudo = None, ""
    for pagina in re.findall(r"<page\b.*?</page>", cajas or "", re.S):
        bloques = []
        for x0, y0, x1, y1, contenido in re.findall(
                r'<block xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</block>', pagina, re.S):
            texto = clean_text(" ".join(re.findall(r">([^<]+)</word>", contenido)))
            texto = re.sub(r"(\w)- (\w)", r"\1\2", texto)
            bloques.append((float(x0), float(y0), float(x1), float(y1), texto))
        titulos = sorted((y0, _ANIO_DISENO.match(t)) for x0, y0, x1, y1, t in bloques if _ANIO_DISENO.match(t))
        regimenes = [(x0, y0, y1) for x0, y0, x1, y1, t in bloques if _REGIMEN_DISENO.match(t)]
        if not titulos and anio is None:
            continue
        for x0, y0, x1, y1, texto in sorted(bloques, key=lambda b: b[1]):
            previos = [m for y, m in titulos if y < y0]
            if previos:
                anio = _ORDINALES_UHIBA[previos[-1].group(1).lower()]
            if not anio or _NO_ES_UNIDAD.match(texto) or _ANIO_DISENO.match(texto) or _REGIMEN_DISENO.match(texto):
                continue
            # A term's block to its right, at its height: a row of the table.
            if any(rx > x1 and ry0 <= y1 + 4 and ry1 >= y0 - 4 and rx - x1 < 200 for rx, ry0, ry1 in regimenes):
                # A name's end in a block of its own ("Física experi-" / "mental 1",
                # "(UCO)") goes on from the one above it.
                if (texto[:1].islower() or texto.startswith("(")) and materias and materias[-1][1] == anio:
                    # (A word cut at the page's foot, "experi-" / "mental 1", is one word.)
                    junta = "" if crudo.endswith("-") else " "
                    materias[-1] = (f"{materias[-1][0]}{junta}{texto}", anio)
                else:
                    antes = len(materias)
                    _agregar(materias, texto, anio)
                    # A table's cell may name a unit at length ("Historia Latinoamericana I:
                    # de la crisis del orden colonial a la conformación de los Estados
                    # nacionales"): the row it sits in says it is one.
                    if len(materias) == antes and 14 < len(texto.split()) <= 25:
                        materias.append((texto, anio))
                crudo = texto
    # The institution's elective space, written in full or by its initials, is one.
    if any(m.startswith("Espacio de Opción Institucional") for m, _ in materias):
        materias = [m for m in materias if m[0] != "EOI"]
    return desde_el_primero(sorted(materias, key=lambda m: m[1]))


plan_diseno_pba.cajas = True


def plan_ude(texto_con_columnas: str) -> list[tuple[str, int]]:
    """Universidad del Este's plans (``pdftotext -layout``, one page): two
    columns, "1· CUATRIMESTRE" and "2· CUATRIMESTRE", and the year a number
    at the left margin ("1"), alone or on its first row. A row is cut where
    the second column starts; a name that goes on below, in lower case
    ("Comunicación en Lengua Inglesa" / "para Turismo I"), is one; "-" is an
    empty cell. The plan ends at the degrees ("Título de Grado")."""
    columna = None
    filas: list[list] = []
    ultima: dict[int, list] = {}
    anio = None
    for linea in texto_con_columnas.splitlines():
        if columna is None:
            encabezado = re.search(r"2\s*[·°º.]\s*CUATRIMESTRE", linea)
            if encabezado and re.search(r"1\s*[·°º.]\s*CUATRIMESTRE", linea):
                columna = encabezado.start()
            continue
        if re.match(r"(?i)\s*t[íi]tulo", linea):
            break
        numero = re.match(r"^\s*(\d)(?=\s{2,}|\s*$)", linea)
        if numero:
            anio, ultima = int(numero.group(1)), {}
            linea = " " * numero.end() + linea[numero.end():]
        if not anio or not linea.strip():
            continue
        for lado, parte in enumerate((linea[:columna], linea[columna:])):
            parte = clean_text(parte)
            if not parte or parte in "-–":
                continue
            if parte[:1].islower() and lado in ultima:
                ultima[lado][0] += " " + parte
            else:
                ultima[lado] = [parte, anio]
                filas.append(ultima[lado])
    materias: list[tuple[str, int]] = []
    for nombre, anio_de_la_fila in filas:
        _agregar(materias, nombre, anio_de_la_fila)
    # An adjective alone ("Turísticos", "Educativas") is the end of a name
    # wrapped in capitals ("Formulación y Evaluación de Proyectos" /
    # "Turísticos"): the rows cannot be told apart, so no plan.
    if any(re.fullmatch(r"(?i)\w+(?:ístic|ativ|iv|ic)[oa]s", n) and n.lower() != "estadísticas"
           for n, _ in materias):
        return []
    return desde_el_primero(materias)


_ANIO_UNPILAR = re.compile(r"(?i)^\s*(\d)\s*(?:er|do|ro|to|°|º)\s*año\b")
_MATERIA_UNPILAR = re.compile(r"^\s*\d{1,2}\s+(\S.*?)\s{2,}\d+\b")


def plan_unpilar(texto_con_columnas: str) -> list[tuple[str, int]]:
    """UNPilar's plans (``pdftotext -layout``): a heading per term ("1er Año
    | Primer cuatrimestre"), a numbered row per subject with its hours and
    credits ("1  Introducción al laboratorio.  48  7"). A long name starts
    on the line above, in the name's column ("Taller de formulación y
    desarrollo de" over "23  proyectos sociocomunitarios.")."""
    materias: list[tuple[str, int]] = []
    anio, anterior = None, ""
    for linea in texto_con_columnas.splitlines():
        encabezado = _ANIO_UNPILAR.match(linea)
        if encabezado:
            anio, anterior = int(encabezado.group(1)), ""
            continue
        materia = _MATERIA_UNPILAR.match(linea)
        if anio and materia:
            nombre = materia.group(1)
            if nombre[:1].islower() and re.match(r"^\s{0,12}[A-ZÁÉÍÓÚÑa-záéíóúñ]", anterior) \
                    and not re.search(r"\d", anterior):
                nombre = f"{anterior.strip()} {nombre}"
            _agregar(materias, nombre, anio)
        if linea.strip():
            anterior = linea
    return desde_el_primero(materias)


_ANIO_IUCBC = re.compile(r"^\s*(PRIMER|SEGUNDO|TERCER|CUARTO|QUINTO|SEXTO)\s+AÑO\s*$")
_MATERIA_IUCBC = re.compile(r"^(\S.*?)\s{2,}[A-Z/]{2,8}\s+\d+\s*hs\b")
# Enfermería's: area, number, name ("AP   1   Enfermería Comunitaria I").
_MATERIA_IUCBC_NUMERADA = re.compile(r"^\s*[A-Z]{2,4}\s+\d{1,2}\s+(\S.*?)\s*$")


_FILA_UNAHUR = re.compile(r"^\s*(PRIMER|SEGUNDO|TERCER|CUARTO|QUINTO|SEXTO)\s+A[ÑN]O\s+(.*?)\s+(Cuatrimestral|Anual|Bimestral|Semestral)\b")
_NUMEROS_AL_FINAL = re.compile(r"(\s+[\d.,]+)+\s*$")


def plan_unahur(texto_con_columnas: str) -> list[tuple[str, int]]:
    """UNAHUR's plan PDFs (``pdftotext -layout``): a table whose rows read
    "PRIMER AÑO  Química  Cuatrimestral  4 64 86 150 6". A name too long for
    its cell wraps around the row: the row has the year and the régimen but
    no name, and the name is the line above joined to the line below (less
    the hours that line carries)."""
    lineas = texto_con_columnas.splitlines()
    materias: list[tuple[str, int]] = []
    for i, linea in enumerate(lineas):
        fila = _FILA_UNAHUR.match(linea)
        if not fila:
            continue
        anio = _ORDINALES[fila.group(1).lower()]
        nombre = fila.group(2).strip()
        if not nombre:
            arriba = lineas[i - 1].strip() if i else ""
            abajo = _NUMEROS_AL_FINAL.sub("", lineas[i + 1]).strip() if i + 1 < len(lineas) else ""
            nombre = f"{arriba} {abajo}".strip()
        _agregar(materias, nombre, anio)
    return desde_el_primero(materias) or _plan_unahur_por_area(lineas)


_ANIO_SOLO_UNAHUR = re.compile(r"^\s*(PRIMER|SEGUNDO|TERCER|CUARTO|QUINTO|SEXTO)\s+A[ÑN]O\s*$")
_AREA_UNAHUR = re.compile(r"\s(C[A-Z]{1,3})\s+[ACB]\s+\d")


def _plan_unahur_por_area(lineas: list[str]) -> list[tuple[str, int]]:
    """UNAHUR's other layout (its licenciaturas): "PRIMER AÑO" alone over
    rows "3   Biología   CFE   C   4   64 ...": the number, the name, the
    subject's field (CFB, CFE, CIC...) and its régimen. A wrapped name runs
    from the line above to the one below, which carries the row's number."""
    materias: list[tuple[str, int]] = []
    anio = None
    for i, linea in enumerate(lineas):
        encabezado = _ANIO_SOLO_UNAHUR.match(linea)
        if encabezado:
            nuevo = _ORDINALES[encabezado.group(1).lower()]
            # The first year again: another plan's table (the intermediate
            # degree's), not this one's.
            if materias and nuevo <= max(a for _, a in materias):
                break
            anio = nuevo
            continue
        area = _AREA_UNAHUR.search(linea)
        if not anio or not area:
            continue
        nombre = re.sub(r"^\s*\d{1,3}\s+", "", linea[:area.start()]).strip()
        if not nombre:
            arriba = lineas[i - 1].strip() if i else ""
            abajo = re.sub(r"^\s*\d{1,3}\s+", "", lineas[i + 1]).strip() if i + 1 < len(lineas) else ""
            nombre = f"{arriba} {abajo}".strip()
        _agregar(materias, nombre, anio)
    return desde_el_primero(materias)


def plan_iucbc(texto_con_columnas: str) -> list[tuple[str, int]]:
    """IUCBC's plans (``pdftotext -layout``): a heading per year ("PRIMER
    AÑO"), then a row per subject with its area and hours ("Química General
    I   AFB   80 hs"), or its area and number ("AP  1  Enfermería
    Comunitaria I")."""
    materias: list[tuple[str, int]] = []
    anio = None
    for linea in texto_con_columnas.splitlines():
        encabezado = _ANIO_IUCBC.match(linea)
        if encabezado:
            anio = _ORDINALES_UHIBA[encabezado.group(1).lower()]
            continue
        materia = _MATERIA_IUCBC.match(linea) or _MATERIA_IUCBC_NUMERADA.match(linea)
        if anio and materia:
            _agregar(materias, materia.group(1), anio)
    return desde_el_primero(materias)


_ANIO_IUPA = re.compile(r"^\s*(PRIMER|SEGUNDO|TERCER|CUARTO|QUINTO|SEXTO)\s+A[ÑN]O\s*$")
# "01   Educación Musical I   2   64   X", " 7   Trabajo corporal complementario I 2   64":
# the code, the name up to the hours.
_FILA_IUPA = re.compile(r"^\s*(\d{1,2})\s+(.*)$")
_HORAS_IUPA = re.compile(r"\d+(?:,\d)?\s+\d+\b")
# An orientation's own subject ("01-1", "02-2") and the "o" between two of them.
_ORIENTACION_IUPA = re.compile(r"^\s*(\d{2}-\d|[oO])\s")
# A piece of name that is not done: it ends on a joining word or an open mark.
_SIN_TERMINAR_IUPA = re.compile(r"(?i)(\b(de|del|y|e|en|la|las|los|el|por|con|para|a|al|o)|[:(-])$")
# (Past the name, the columns: hours, terms, prerequisites, "o 08-2" among them.)
_RESTO_IUPA = re.compile(r"^\s{4,}([A-Za-zÁÉÍÓÚÑáéíóúñ(][^\d●]*?)\s*(?:\s{2,}(?:[●Xx\d]|o\s+\d).*)?$")


def plan_iupa(texto_con_columnas: str) -> list[tuple[str, int]]:
    """IUPA's plans (``pdftotext -layout``): "PRIMER AÑO" alone over rows
    "01   Educación Musical I   2   64   X   06": the code, the name, its
    hours, its term and its prerequisites. An orientation's own subjects
    ("01-1 Canto I (sólo orientación en Canto)") are not the plan every
    student takes, and the free hours are not a subject."""
    def anio_de(linea: str) -> int | None:
        encabezado = _ANIO_IUPA.match(linea)
        return _ORDINALES[encabezado.group(1).lower()] if encabezado else None

    # The name runs up to the hours (a justified name has wide gaps:
    # "Taller     Educación    mediada       por").
    return _filas_con_codigo(texto_con_columnas, anio_de, re.compile(r"\s+(?=\d+(?:,\d)?\s+\d+\b)|\s{2,}(?=[●Xx\d])"),
                             _HORAS_IUPA, _RESTO_IUPA)


_ANIO_CON_NUMERO = re.compile(r"^\s*(\d)\s*[º°]\s*A[ñn]o\s*$")
_REGIMEN_DE_FILA = r"(?:Anual|Cuatrimestral|Semestral)\b"
_PIEZA_CON_REGIMEN_DE_FILA = re.compile(r"^\s{4,}([A-Za-zÁÉÍÓÚÑáéíóúñ(][^\d●]*?)\s*(?:\s{2,}(?:" + _REGIMEN_DE_FILA + r"|\d).*)?$")


def plan_estructura_con_regimen(texto_con_columnas: str) -> list[tuple[str, int]]:
    """A design's structure as rows "9   Práctica Docente I ...   Anual
    Taller   5 horas" under "1º Año" (Corrientes' Primaria): the unit's
    number, its name up to its régimen, its format and hours. The
    institution's own slot ("Propuesta variable o complementaria 1") is not
    a unit of the plan."""
    def anio_de(linea: str) -> int | None:
        encabezado = _ANIO_CON_NUMERO.match(linea)
        return int(encabezado.group(1)) if encabezado else None

    materias = _filas_con_codigo(texto_con_columnas, anio_de, re.compile(r"\s{2,}(?=" + _REGIMEN_DE_FILA + ")"),
                                 re.compile(_REGIMEN_DE_FILA), _PIEZA_CON_REGIMEN_DE_FILA, sangria=30)
    return desde_el_primero([(n, a) for n, a in materias if not re.match(r"(?i)propuesta variable", n)])


def _filas_con_codigo(texto_con_columnas: str, anio_de: Any, corte: re.Pattern, datos: re.Pattern,
                      pieza_re: re.Pattern, sangria: int = 1000) -> list[tuple[str, int]]:
    """Rows of a plan numbered under each year's heading, the name before
    the row's other columns (``corte`` ends it; ``datos`` is what a row
    without a name starts with). A name too long for its cell wraps: it
    goes on in the line below when it is not done (it ends on "de", "y", an
    open bracket, or the row's other columns went to a line of their own),
    or it starts in the line above when the row's own part is none or
    starts in lower case ("Taller integrado de procedimientos y" over
    "05   técnicas del lenguaje visual I"). A loose piece further right than
    ``sangria`` is another column's, not a name's."""
    filas: list[dict] = []
    anio = None
    ultima = -2  # the line the last row's name was last seen on
    pendiente: tuple[int, str] | None = None  # a loose piece of name, and its line
    for i, linea in enumerate(texto_con_columnas.splitlines()):
        nuevo = anio_de(linea)
        if nuevo:
            anio, pendiente = nuevo, None
            continue
        if not anio:
            continue
        fila = _FILA_IUPA.match(linea)
        if re.fullmatch(r"\s*\d+(?:,\d)?\s+\d+[\s\d,●Xx]*", linea) and filas and ultima == i - 1:
            ultima = i  # the row's hours on a line of their own: its name may go on below
            continue
        if fila and not _ORIENTACION_IUPA.match(linea):
            resto = fila.group(2).strip()
            propio = " ".join(corte.split(resto)[0].split())
            if not re.match(r"[A-Za-zÁÉÍÓÚÑáéíóúñ(]", propio) or datos.match(propio):
                if not datos.match(resto):
                    continue  # a page's number
                propio = ""
            partes = [propio]
            arriba = bool(pendiente and pendiente[0] == i - 1 and (
                not propio or propio[0].islower() or _SIN_TERMINAR_IUPA.search(pendiente[1])))
            if arriba:
                partes.insert(0, pendiente[1])
            # A name begun above the row is likely to end below it, too.
            filas.append({"partes": partes, "anio": anio, "abierta": not propio or arriba or not datos.search(resto)})
            ultima, pendiente = i, None
            continue
        if re.fullmatch(r"[\s\d,●Xx]*", linea):
            # The row's hours on a line of their own: its name may go on below.
            if filas and ultima == i - 1 and linea.strip():
                ultima = i
            continue
        pieza = pieza_re.match(linea)
        if (not pieza or pieza.start(1) > sangria or _ORIENTACION_IUPA.match(linea)
                or re.match(r"(?i)\s*total\b", linea)):
            pendiente = None
            continue
        texto = " ".join(pieza.group(1).split())
        if filas and ultima == i - 1:
            previo = " ".join(p for p in filas[-1]["partes"] if p)
            if (filas[-1]["abierta"] or texto[0].islower() or texto[0] == "("
                    or previo.count("(") > previo.count(")")
                    or _SIN_TERMINAR_IUPA.search(previo)):
                if re.fullmatch(r"[a-zá-ú]{1,2}", texto):
                    # A word's last letter on the next line ("Tecnología" / "s").
                    filas[-1]["partes"][-1] += texto
                else:
                    filas[-1]["partes"].append(texto)
                filas[-1]["abierta"] = False
                ultima = i
                continue
        pendiente = (i, texto)
    materias: list[tuple[str, int]] = []
    for fila in filas:
        nombre = " ".join(p for p in fila["partes"] if p)
        # "Tecnología s": a word's last letter set apart in the source.
        nombre = re.sub(r"(\w{4,}) ([a-zá-ú])$", r"\1\2", nombre)
        # A footnote's mark: "Instrumento Aplicado B II   (a)", "Folklore *".
        nombre = re.sub(r"\s*(?:\([a-z]\)|\*+)$", "", nombre)
        if nombre and not re.match(r"(?i)horas de asignaci[óo]n libre", nombre):
            _agregar(materias, nombre, fila["anio"])
    return desde_el_primero(materias)


_ANIO_DE_TABLA = re.compile(r"(?i)^\s*(primer|segundo|tercer|cuarto|quinto|sexto)\s+año\b")
_COLUMNA_DE_UNIDADES = re.compile(r"(?i)^(unidades?|espacios?)\s+curricular(es)?$|^asignaturas?$")


def plan_tablas_por_anio(ruta: str) -> list[tuple[str, int]]:
    """A design laid out as a table per year (``pdfplumber``), the year in
    its first row ("PRIMER AÑO (1056 horas cátedras – 704 horas reloj)") and
    a column of its units ("UNIDADES CURRICULARES"; Santiago del Estero's
    Primaria). The institution's own slots ("1 espacio cuatrimestral") are
    not a unit of the plan."""
    import pdfplumber

    materias: list[tuple[str, int]] = []
    with pdfplumber.open(ruta) as pdf:
        for pagina in pdf.pages:
            for tabla in pagina.extract_tables():
                filas = [[" ".join((c or "").split()) for c in fila] for fila in tabla]
                anio = next((_ORDINALES[m.group(1).lower()] for fila in filas[:1] for c in fila
                             if (m := _ANIO_DE_TABLA.match(c))), None)
                columna = next(((i, j) for i, fila in enumerate(filas[:4]) for j, c in enumerate(fila)
                                if _COLUMNA_DE_UNIDADES.match(c)), None)
                if not anio or not columna:
                    continue
                for fila in filas[columna[0] + 1:]:
                    nombre = fila[columna[1]] if columna[1] < len(fila) else ""
                    if nombre and not re.match(r"(?i)^\d+\s+espacios?\b", nombre):
                        _agregar(materias, nombre, anio)
    return desde_el_primero(materias)


plan_tablas_por_anio.ruta = True  # type: ignore[attr-defined]


_ANIO_UHIBA = re.compile(r"(?i)^\s+(primer|segundo|tercer|cuarto|quinto|sexto)\s+año\s*$")


def plan_uhiba(texto_con_columnas: str) -> list[tuple[str, int]]:
    """The Hospital Italiano's plans (``pdftotext -layout``): a heading per
    year ("Primer año"), then a record per subject: a yearly one on one
    line ("Biofísica  Anual  128 ..."), a term's from the line that names
    the term ("Primer", "Segundo") to the one that ends it ("cuatrimestre"),
    its hours on any of them. The name is the text at the left margin of
    the record's lines ("Módulo Integrador" / "Fisicomatemático"). A year's
    totals are not a subject."""

    def margen(linea: str) -> str:
        # (A wrapped name's first line may start a space in: " Módulo Integrador".)
        texto = re.split(r"\s{2,}", linea.strip())[0] if re.match(r"\s{0,3}\S", linea) else ""
        return "" if re.fullmatch(r"(?i)anual|primer|segundo|cuatrimestral|cuatrimestre|[\d-]+", texto) else texto

    materias: list[tuple[str, int]] = []
    anio, registro = None, []

    def cerrar() -> None:
        nombre = clean_text(" ".join(filter(None, (margen(l) for l in registro))))
        if anio and nombre and not re.search(r"\d", nombre):
            _agregar(materias, nombre, anio)
        registro.clear()

    for linea in texto_con_columnas.splitlines():
        if not linea.strip():
            continue
        encabezado = _ANIO_UHIBA.match(linea)
        if encabezado or re.match(r"(?i)\s*totales\b", linea):
            registro.clear()
            anio = _ORDINALES_UHIBA[encabezado.group(1).lower()] if encabezado else anio
            continue
        if not anio:
            continue
        # A yearly subject ends on its line, its name maybe begun on the one before.
        if re.search(r"(?i)\S\s{2,}(anual|cuatrimestral)\s{2,}\d", linea):
            registro.append(linea)
            cerrar()
            continue
        registro.append(linea)
        if re.search(r"(?i)\bcuatrimestre\b", linea):
            cerrar()
    return desde_el_primero(materias)


_ORDINALES_UHIBA = {"primer": 1, "segundo": 2, "tercer": 3, "cuarto": 4, "quinto": 5, "sexto": 6}


_SIU_MATERIA = re.compile(r"^\s*(\d{1,2}) - [A-Za-zÁÉÍÓÚáéíóú ]+?\s{2,}\d{3,6} (.+?)(?:\s{2,}\d+)?\s{2,}[SN]\s")
_SIU_ORIENTACION = re.compile(r"^\s*Orientaci[óo]n \d+\s+(.+?)\s*$")


def plan_siu_guarani(texto_con_columnas: str) -> list[tuple[str, int]]:
    """The plan report SIU Guaraní prints ("Plan de Estudios", ``pdftotext
    -layout``): a row per subject, "1 - Primer Cuatrimestre  15802
    Arqueología General  6  S  0  Normal", its name wrapped onto the next
    line when long; the rows under it ("Para Cursarla debe tener ...") are
    its prerequisites. A plan with orientations lists each one after the
    common trunk ("Orientación 001  Teoría y Metodología ..."), repeating
    the subjects all share: the plan is the trunk and what every
    orientation has; an orientation's own subjects are a choice."""
    # The plan of one orientation of the career ("Carrera: 073 Tecnicatura
    # Superior en Interpretación Musical Orientación: Arpa") is not the
    # career's.
    if re.search(r"(?im)^\s*Carrera:.*\bOrientaci[óo]n:", texto_con_columnas):
        return []
    tronco: list[tuple[str, int]] = []
    orientaciones: dict[str, list[tuple[str, int]]] = {}
    actual: list[tuple[str, int]] = tronco
    ultima = None
    for linea in texto_con_columnas.splitlines():
        orientacion = _SIU_ORIENTACION.match(linea)
        if orientacion:
            actual = orientaciones.setdefault(orientacion.group(1), [])
            ultima = None
            continue
        materia = _SIU_MATERIA.match(linea)
        if materia:
            actual.append((clean_text(materia.group(2)), int(materia.group(1))))
            ultima = len(actual) - 1
            continue
        # A name wrapped onto the next line: text alone, under the name.
        if (ultima is not None and re.match(r"^\s{30,}[A-Za-zÁÉÍÓÚáéíóú]", linea)
                and not re.search(r"\d{3,6}|Para (Cursarla|Aprobarla)|Plan de Estudios", linea)):
            nombre, anio = actual[ultima]
            actual[ultima] = (f"{nombre} {clean_text(linea)}", anio)
        if linea.strip():
            ultima = None if not re.match(r"^\s{30,}", linea) else ultima
    comunes = None
    for materias in orientaciones.values():
        nombres = {m for m, _ in materias}
        comunes = nombres if comunes is None else comunes & nombres
    plan: list[tuple[str, int]] = []
    for nombre, anio in tronco + [m for materias in orientaciones.values() for m in materias
                                   if m[0] in (comunes or set())]:
        # A requirement is not a subject ("Requisito: Idioma Moderno",
        # "Prueba de Suficiencia de Inglés").
        if not re.match(r"(?i)requisito\b|prueba de suficiencia\b", nombre):
            _agregar(plan, nombre, anio)
    return desde_el_primero(sorted(plan, key=lambda m: m[1]))


_CUATRIMESTRE_ROMANO = {r: i for i, r in enumerate(
    ("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"), start=1)}


def _plan_unlu(html: str) -> list[tuple[str, int]]:
    """UNLu: tables headed "Cuat" ("Cuat.", "Cuat. (1)"), a row per subject:
    its term in roman numerals on the first row of the term ("III", spanning
    the rows under it), its five-digit code, and its name in the cell after
    the code. The year is the term's pair (terms I and II, the first). A row
    with no term ("-": the introductory workshop, the language and computing
    requirements) is not in a year, and footnote marks ("(2)", "(a)") and a
    yearly subject's second term ("(Anual)", "(Continuación)") are not
    names."""
    materias: list[tuple[str, int]] = []
    # A second table that counts its terms from I again is the cycle after
    # the intermediate degree (Administración: 8 terms, then "I", "II"): its
    # terms follow the first table's.
    hasta, desde = 0, 0
    for tabla in BeautifulSoup(html or "", "html.parser").find_all("table"):
        filas = tabla.find_all("tr")
        encabezado = [_texto(c) for c in filas[0].find_all(["td", "th"])] if filas else []
        if not encabezado or not encabezado[0].startswith("Cuat"):
            continue
        cuatrimestre, primero = None, True
        for fila in filas[1:]:
            celdas = [_texto(c) for c in fila.find_all(["td", "th"])]
            codigo = next((i for i, c in enumerate(celdas) if re.match(r"\d{5}\b", c)), None)
            if codigo is None or codigo + 1 >= len(celdas):
                continue
            if codigo == 1:
                cuatrimestre = _CUATRIMESTRE_ROMANO.get(celdas[0])
                if cuatrimestre and primero:
                    desde, primero = (hasta if cuatrimestre <= hasta else 0), False
                if cuatrimestre:
                    cuatrimestre += desde
                    hasta = max(hasta, cuatrimestre)
            nombre = re.sub(r"(?i)\s*\(anual\)", "", celdas[codigo + 1])
            nombre = re.sub(r"(?i)(\s*-\s*continuaci[óo]n|\s*\((\d{1,2}|[a-z]|continuaci[óo]n)\))+$", "", nombre)
            if cuatrimestre and nombre and nombre.lower() not in {m.lower() for m, _ in materias}:
                _agregar(materias, nombre, (cuatrimestre + 1) // 2)
    return materias


def _anios_declarados_unlu(html: str) -> float | None:
    """The years the page's first table states ("5 años", "5 1/2 años"),
    when it states them in years."""
    tabla = BeautifulSoup(html or "", "html.parser").find("table")
    filas = tabla.find_all("tr") if tabla else []
    if len(filas) < 2:
        return None
    encabezado = [_texto(c) for c in filas[0].find_all(["td", "th"])]
    celdas = [_texto(c) for c in filas[1].find_all(["td", "th"])]
    if "Duración" not in encabezado or len(celdas) != len(encabezado):
        return None
    anios = re.fullmatch(r"(?i)(\d+)(\s+1/2)?\s+años", celdas[encabezado.index("Duración")])
    return int(anios.group(1)) + (0.5 if anios.group(2) else 0) if anios else None


def plan_ucongreso(html: str) -> list[tuple[str, int]]:
    """Universidad de Congreso, in its first set of tabs (the second is its
    campuses) a ``p.materia`` per subject, each followed by the campuses
    that teach it (links in a hidden span, not subjects). Two layouts: a tab
    per year ("1º AÑO"), or tabs of plans ("Plan", "Plan 2018"), the first
    the one in force, where "Primer Año" heads each year's lines."""
    tabs = BeautifulSoup(html or "", "html.parser").select_one(".careers-tabs")
    if not tabs:
        return []
    # A year by orientation ("4º AÑO - Instituciones", Ciencias de la
    # Educación): several plans, none read.
    if any(re.match(r"(?i)\s*\d\s*[º°]\s*año\s*-", _texto(e)) for e in tabs.select(".tab-labels .tab-label")):
        return []
    etiquetas = {e.get("data-tabs-number"): anio_de(_texto(e)) for e in tabs.select(".tab-labels .tab-label")}
    materias: list[tuple[str, int]] = []
    for contenido in tabs.select(".tab-contents > .tab-content"):
        anio = etiquetas.get(contenido.get("data-tabs-number"))
        por_anio = bool(anio)
        for linea in contenido.select(".materias > p.materia"):
            # "Administración I (*)": promoted; "(*) Régimen promocional: 12
            # espacios curriculares" and "1º SEMESTRE" are notes and headings.
            texto = re.sub(r"\s*\(\*\)$", "", _texto(linea).lstrip("+- ").strip())
            if not por_anio and anio_de(texto):
                anio = anio_de(texto)
            elif anio and not re.match(r"(?i)\(\*\)|\d\s*[°º]?\s*semestre$", texto):
                _agregar(materias, texto, anio)
        # Of tabs of plans, only the first: the one in force.
        if not por_anio:
            break
    return desde_el_primero(materias)


def plan_fbqf_unt(html: str) -> list[tuple[str, int]]:
    """UNT Bioquímica, Química y Farmacia (fbqfuntedu.ar): under "#plan", a
    tab per year titled "1er año" (``data-title-tab-id``), its pane (the same
    ``data-tab-id``, not the year: Química's run 1, 2, 3, 4, 6) holding a
    table per term: "Asignatura", "Regimen", "Correlativas"."""
    plan = BeautifulSoup(html or "", "html.parser").find(id="plan")
    if not plan:
        return []
    anio_de_la_pestana = {t["data-title-tab-id"]: anio_de(t.get_text("", strip=True))
                          for t in plan.find_all(attrs={"data-title-tab-id": True})}
    materias: list[tuple[str, int]] = []
    for tabla in plan.find_all("table"):
        panel = tabla.find_parent(attrs={"data-tab-id": True})
        anio = anio_de_la_pestana.get(panel["data-tab-id"]) if panel else None
        if not anio:
            continue
        for fila in tabla.find_all("tr"):
            celdas = [_texto(c) for c in fila.find_all(["td", "th"])]
            # "Demostrar conocimiento de Inglés Técnico": a requirement.
            if celdas and celdas[0] and not re.match(r"(?i)asignatura$|demostrar\b", celdas[0]):
                _agregar(materias, celdas[0], anio)
    return desde_el_primero(materias)


def plan_unlu(html: str) -> list[tuple[str, int]]:
    # A plan whose years are not the ones the page states is part of one
    # (Biológicas: 5 1/2 years stated, four read).
    materias = desde_el_primero(_plan_unlu(html))
    declarados = _anios_declarados_unlu(html)
    ultimo = max((anio for _, anio in materias), default=0)
    if declarados and not (int(declarados) <= ultimo <= math.ceil(declarados)):
        return []
    return materias


def _plan_unnoba(html: str) -> list[tuple[str, int]]:
    """UNNOBA's plans (planesdeestudio.unnoba.edu.ar): a heading per year
    ("1º Año") and a button per subject, its code in brackets ("Elementos de
    Matemática (01374)"). An elective's options, listed in a dialog under
    "Posibles:", are not the plan: the elective's own slot is."""
    materias: list[tuple[str, int]] = []
    anio = None
    for elemento in BeautifulSoup(html or "", "html.parser").find_all(["h2", "button"]):
        if elemento.find_parent("dialog") or elemento.find_parent("ul"):
            continue
        if elemento.name == "h2":
            numero = re.fullmatch(r"(\d)\s*º\s*Año", _texto(elemento))
            anio = int(numero.group(1)) if numero else None
            continue
        nombre = elemento.find("p")
        if anio and nombre and "subject" in (elemento.get("class") or []):
            _agregar(materias, re.sub(r"\s*\([A-Z]{0,2}\d{3,5}\)$", "", _texto(nombre)), anio)
    return materias


def plan_unnoba(html: str) -> list[tuple[str, int]]:
    return desde_el_primero(_plan_unnoba(html))


def _plan_untdf(html: str) -> list[tuple[str, int]]:
    """UNTDF: the plan's table, a section row per year ("Año 1") and a row
    per subject under it. A section that is not a year (electives) is not
    the plan."""
    materias: list[tuple[str, int]] = []
    tabla = BeautifulSoup(html or "", "html.parser").select_one("table.untdf-study-plan__table")
    anio = None
    for fila in tabla.select("tr") if tabla else []:
        if "untdf-study-plan__section-row" in (fila.get("class") or []):
            numero = re.fullmatch(r"(?i)año\s+(\d)", _texto(fila))
            anio = int(numero.group(1)) if numero else None
            continue
        nombre = fila.select_one(".untdf-study-plan__subject")
        if anio and nombre:
            _agregar(materias, _texto(nombre), anio)
    return materias


def plan_untdf(html: str) -> list[tuple[str, int]]:
    return desde_el_primero(_plan_untdf(html))


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


# A table's legend, not a subject: "Anual", "1.º Cuatrimestre", "Materias
# anuales", "Materia cuatrimestral", "** ...", "Materias Electivas (no
# obligatorias)".
_LEYENDA = re.compile(r"(?i)^(\*|anual(es)?$|cuatrimestral(es)?$|semestral(es)?$|\d\.?\s*[º°]?\s*cuatrimestre$|ciclo de especializaci|(primer|segundo)\s+(semestre|cuatrimestre)$|"
                      r"materias? (anual|cuatrimestral|semestral|electiva)|materias electivas)")


_FIN_DEL_PLAN = re.compile(r"(?i)^(disposici[óo]n|resoluci[óo]n|res\.|requisitos|t[íi]tulo|modalidad|duraci[óo]n|"
                           r"inscrib|materias optativas|optativas|electivas|perfil|alcances|autorizad|plan de estudios? tentativo|"
                           r"ver correlatividades|plan de estudios?$|¿|para finalizar la carrera|en \w+ vas a encontrar|"
                           r"descarg|quiero recibir|aclaraciones$|ingreso \d{4}$|contacta a nuestr|todos los derechos|autoridades$|¡?quiero inscribirme)")


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
    anio, guiones = None, False
    for linea in lineas[inicio + 1:] if inicio is not None else []:
        if re.fullmatch(r"(?i)\d+\s*[º°o]?\s*año|\w+\s+año", linea) and anio_de(linea):
            anio = anio_de(linea)
        elif re.search(r"(?i)cuatrimestre|semestre", linea) and len(linea.split()) <= 3 or _LEYENDA.match(linea):
            continue
        elif anio and _FIN_DEL_PLAN.match(linea):
            break
        elif anio:
            # UNSTA marks each subject annual or by term: "– A Formación
            # Humanística I"; on such a page a line without the dash ends the plan.
            con_guion = re.match(r"^[–-]\s*", linea)
            if guiones and not con_guion:
                break
            guiones = guiones or (bool(con_guion) and not materias)
            _agregar(materias, re.sub(r"^[–-]\s*(?:[AC]\s+)?", "", linea), anio)
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
        # The design careers head each table with its year: "SEGUNDO AÑO –
        # CICLO DE FORMACIÓN INICIAL", "PRIMER AÑO – CBC".
        ordinal = re.match(r"(?i)(primer|segundo|tercer|cuarto|quinto|sexto)\s+a[ñn]o\b", titulo)
        if ordinal and anio is None:
            anio = ("primer", "segundo", "tercer", "cuarto", "quinto", "sexto").index(ordinal.group(1).lower()) + 1
        # ...or "2º año", "Ciclo Básico Común – 1º año".
        cifra = re.search(r"(?i)\b(\d)\s*[º°]\s*a[ñn]o\b", titulo)
        if cifra and anio is None:
            anio = int(cifra.group(1))
        for fila in tabla.find_all("tr") if anio else []:
            celdas = [_texto(c) for c in fila.find_all(["td", "th"])]
            if len(celdas) < 3 or celdas[0].lower() == "materia" or not celdas[1]:
                continue
            # The CBC's "Intr. al ..." is a shortened word, not a code.
            nombre = re.sub(r"^Intr\.\s+", "Introducción ", celdas[0])
            nombre = re.sub(r"^[A-Z][A-Za-z0-9]{0,4}\.\s+", "", nombre)
            # Without a footnote's mark, "(*)" or "(1)"; a subject a note
            # lets be taken in either of two years (Diseño Gráfico's
            # "Morfología II (1)") is kept in the first.
            nombre = re.sub(r"\s*\((?:\*+|\d)\)$", "", nombre.replace("\xa0", " ")).strip()
            if re.search(r"(?i)optativ|electiv", nombre) or comparison_key(nombre) in {
                    comparison_key(n) for n, _ in materias}:
                continue
            _agregar(materias, nombre, anio)
    return materias


def plan_fadu(html: str) -> list[tuple[str, int]]:
    return desde_el_primero(_plan_fadu(html))


def _plan_fba_unlp(html: str) -> list[tuple[str, int]]:
    """UNLP's Bellas Artes and Humanidades: the plan on the career's page,
    each year a heading (". Primer año", "1º AÑO") and its subjects one per
    line, until "+ Ver plan de estudios completo", "Archivos" or the page's
    other parts."""
    soup = BeautifulSoup(html or "", "html.parser")
    for parte in soup.find_all(["nav", "header", "footer", "script", "style"]):
        parte.decompose()
    lineas = [clean_text(l) for l in (soup.body or soup).get_text("\n").split("\n") if clean_text(l)]
    materias: list[tuple[str, int]] = []
    anio = None
    for linea in lineas:
        nuevo = anio_de(re.sub(r"^[.·•]\s*", "", linea))
        if nuevo:
            anio = nuevo
            continue
        if anio is None:
            continue
        if re.match(r"(?i)^\+?\s*ver\s+plan|^(?:requisitos|inscrip|t[íi]tulo|alcances|perfil|contacto|"
                    r"archivos|esquema\s+de\s+correlativas)\b", linea) or len(linea) > 90:
            break
        # A choice among several ("Una MATERIA OPTATIVA A a elegir entre
        # ...", Humanidades) is not a subject of its own.
        if re.match(r"(?i)^(?:una|dos|tres)\s+(?:materias?\s+)?(?:optativas?|capacitaci)", linea) \
                or re.search(r"(?i)\ba\s+elegir\b", linea):
            continue
        _agregar(materias, linea, anio)
    return materias


def plan_fba_unlp(html: str) -> list[tuple[str, int]]:
    return desde_el_primero(_plan_fba_unlp(html))


def plan_fahce_unlp(html: str) -> list[tuple[str, int]]:
    """UNLP's Humanidades: as Bellas Artes, but a row "Una MATERIA OPTATIVA A
    a elegir entre" lists its options inside the cell; one of them is taken,
    not all, so the options go with it."""
    # The list of its chairs, where the page has one, reads cleaner than its
    # tables (Sociología's: "TALLER I (un", "anual- o dos"), though it has no
    # years.
    catedras = _plan_fahce_catedras(html)
    if len(catedras) >= 20:
        return catedras
    soup = BeautifulSoup(html or "", "html.parser")
    for opciones in soup.select("td ul"):
        opciones.decompose()
    materias = plan_fba_unlp(str(soup))
    # A year of more than twelve is the pool of electives the page lists
    # under the last year without saying so (the profesorados' fifth).
    if materias and max(Counter(anio for _, anio in materias).values()) > 12:
        return []
    # A term's heading or a cut "Una" read as a subject (Bibliotecología):
    # the table is not read right.
    if any(re.match(r"(?i)(\d\w*\s+cuatrimestre|una)$", nombre) for nombre, _ in materias):
        return []
    return materias


# A slot of the plan listed among its chairs: "Materia optativa I", "Seminario II".
_HUECO_FAHCE = re.compile(r"(?i)^(materia optativa|optativa|seminario de licenciatura|seminario)\b")
_IDIOMA_SUELTO = re.compile(r"(?i)^(franc[ée]s|italiano|portugu[ée]s|alem[áa]n|ingl[ée]s|lat[íi]n|griego)$")


def _plan_fahce_catedras(html: str) -> list[tuple[str, int | None]]:
    """Humanidades' other layout: the plan as a list of links to its chairs
    (".../catedras/catedra-…"), no years. The subjects everyone takes are in
    capitals; a heading "Cinco OPTATIVAS LIBRES a elegir entre" is followed
    by its options, of which only the slots ("Materia optativa I") are the
    plan's. A language alone is an option of the language requirement."""
    materias: list[str] = []
    for enlace in BeautifulSoup(html or "", "html.parser").find_all("a", href=re.compile(r"/catedras/catedra-\d+")):
        texto = " ".join(enlace.get_text(" ", strip=True).split()).strip(" *")
        letras = [c for c in texto if c.isalpha()]
        if not letras or re.search(r"(?i)elegir|^(una|dos|tres|cuatro|cinco)\s", texto):
            continue
        en_mayusculas = sum(c.isupper() for c in letras) / len(letras) > 0.8
        if not (en_mayusculas or _HUECO_FAHCE.match(texto)):
            continue
        if en_mayusculas:
            from rumbo_scraper.parsers.guias_nacionales import con_tildes

            texto = con_tildes(texto)
        texto = re.sub(r"(?i)\b(i{1,4}|iv|vi{0,3}|ix|x)\b(?=\s|/|$)", lambda m: m.group(1).upper(), texto)
        texto = re.sub(r"/(\w)", lambda m: "/" + m.group(1).upper(), texto)
        texto = re.sub(r"\s([a-e])$", lambda m: " " + m.group(1).upper(), texto)
        # A link broken in two: "FILOSOFÍA" + "DE LAS CIENCIAS".
        if materias and re.match(r"(?i)de\s", texto) and len(materias[-1].split()) == 1:
            materias[-1] = f"{materias[-1]} {texto[0].lower()}{texto[1:]}"
            continue
        if not _IDIOMA_SUELTO.match(texto) and texto not in materias:
            materias.append(texto)
    return [(nombre, None) for nombre in materias]


# What the general reader, reading a page's lines year by year, takes in
# besides the subjects: the terms, the page's foot and its admission papers.
_NO_ES_MATERIA_DEL_ANIO = re.compile(
    r"(?i)^\(?\s*(?:\d\s*[º°erdo.]*\s*)?(?:1er|2do|primer|segundo)?\s*cuatrimestr|^cuatrimestral|^\(?anual\)?$|"
    r"^c[áa]tedra\s+[a-z]\b|^ver\s+plan|^obtiene\s+t[íi]tulo|^comienzan|^dni\b|"
    # The admission papers ("Documentación requerida"), not "Documentación y
    # Registros Médicos I" (Barceló).
    r"^documentaci[óo]n(?:\s+(?:de\s+ingreso|requerida|a\s+presentar|necesaria|para)\b|\s*:|$)|"
    r"^inscrip|^requisitos|^realizado\s+por|copyright|©|^todos\s+los\s+derechos|"
    # A subject's state, a block's heading, the page's asides.
    r"^aprobad[ao]\b|^ciclo\s+(?:medio|superior|final|b[áa]sico|inicial|de\s+licenciatura|profesional|de\s+especializaci[óo]n)$|^optativas\b|"
    r"^poseer\b|^\d+\s+materias$|^programa$|^reconocid|^modificaci|^campus|^coordinador|^ir\s+al|"
    r"^espacios\s+curriculares|^nota\b|^per[íi]odo\s+de|^semanal$|^\d\s*[º°]\s*cuat|cuatrimestre$|"
    r"^incumbenc|^alcances|^perfil|^ordenanza\b|^mat\.\s|"
    # The degree ("Ingeniero/a Químico/a"), a graduate's competence
    # ("Interpretar y reformular…", "Diseñar, desarrollar y evaluar…").
    r"\w/a\b|^[a-záéíóúñ]{4,}(?:ar|er|ir)(?:,|\s+y\s+[a-záéíóúñ]+(?:ar|er|ir)\b)")
_FIN_DE_LA_PAGINA = re.compile(r"(?i)copyright|©|^realizado\s+por|^documentaci[óo]n\s+de\s+ingreso|^¿|"
                               r"^normativa\s+de\s+la\s+carrera|^unidad\s+acad[ée]mica$|"
                               # Barceló: the free activities that follow the plan.
                               r"^espacios\s+acad[ée]micos\s+libres$|"
                               # UNER's faculty pages: the call to enrol, the page's foot.
                               r"^ingreso\s+20\d\d$|^m[áa]s\s+info|^scroll\s+al\s+inicio|^destinatarios$|"
                               r"^\W*descargar\s+plan|^caracter[íi]sticas del plan")


def plan_por_anios(html: str) -> list[tuple[str, int]]:
    """The general reader's plan, year by year, for the sites whose pages it
    reads well (checked by hand, one career each): without the terms, the
    page's foot or its admission papers, beginning in the first year, with ten
    subjects at least and never more than fifteen in a year."""
    from rumbo_scraper.parsers import generico

    materias: list[tuple[str, int]] = []
    for fila in generico.leer_plan(html or ""):
        nombre, anio = fila.get("nombre") or "", fila.get("anio")
        if _FIN_DE_LA_PAGINA.search(nombre):
            break
        if not anio or _NO_ES_MATERIA_DEL_ANIO.search(nombre):
            continue
        # "Lingüística I - CL 2026": the year the chair's programme is of;
        # "1 Introducción a la Arqueología" or "19Fundamentos de Geofísica":
        # its number in the plan; "(C)", "(2do cuatrimestre)"; a leading dash.
        nombre = re.sub(r"\s+-\s+CL\s+\d{4}$|\s*\(C\)$|\s*\((?:\d\s*\w*|1er|2do|primer|segundo)\s+cuatrimestre\)",
                        "", nombre)
        nombre = re.sub(r"^[\u00ad\s\-–·•]+", "", nombre)
        _agregar(materias, re.sub(r"^\d{1,2}(?:\s+|(?=[A-ZÁÉÍÓÚÑ][a-záéíóúñ]))(?=[A-ZÁÉÍÓÚÑ])", "", nombre), anio)
    # "1.01 Introducción a la Contabilidad" (UNER Económicas): where nearly
    # every subject carries its code, one without is an elective offered.
    codigo = re.compile(r"^\d{1,2}\.\d{2}\s+")
    if materias and sum(bool(codigo.match(n)) for n, _ in materias) >= 0.8 * len(materias):
        materias = [(codigo.sub("", n), a) for n, a in materias if codigo.match(n)]
    materias = desde_el_primero(materias)
    if len(materias) < 10 or max(Counter(a for _, a in materias).values()) > 15:
        return []
    return materias


_ANIO_INDICE = {"primer": 1, "segundo": 2, "tercer": 3, "cuarto": 4, "quinto": 5}
_ENTRADA_INDICE = re.compile(r"^(.+?)\s*\.{2,}\s*\d+$")


def plan_indice_pba(carrera: str, texto: str) -> list[tuple[str, int]]:
    """A Province of Buenos Aires design that gives its units in its index
    (the Profesorados de Educación Inicial y Primaria, both in one
    document): under "Contenidos del profesorado de <carrera>", a year
    ("Primer año ....49") and its units, one per line with its page, up to
    "Correlatividades". A unit the index names "X I y II" in two years is
    X I in the first of them and X II in the second."""
    materias: list[tuple[str, int]] = []
    anio = 0
    dentro = False
    for linea in texto.splitlines():
        linea = clean_text(linea.replace("\f", ""))
        if not dentro:
            dentro = bool(re.match(r"(?i)contenidos del profesorado de " + re.escape(carrera) + r"\b.*\.{2,}\s*\d+$", linea))
            continue
        if not linea:
            continue
        entrada = _ENTRADA_INDICE.match(linea)
        if not entrada:
            break
        nombre = entrada.group(1).strip()
        ano = re.match(r"(?i)(primer|segundo|tercer|cuarto|quinto)\s+a[ñn]o$", nombre)
        if ano:
            anio = _ANIO_INDICE[ano.group(1).lower()]
        elif re.match(r"(?i)correlatividades", nombre):
            break
        elif anio:
            materias.append((nombre, anio))
    dobles = [n for n, _ in materias if n.endswith(" I y II")]
    for nombre in set(dobles):
        anios = sorted({a for n, a in materias if n == nombre})
        if len(anios) == 2:
            base = nombre[:-len(" I y II")]
            materias = [(base + (" I" if a == anios[0] else " II"), a) if n == nombre else (n, a) for n, a in materias]
    vistas: set[str] = set()
    unicas = []
    for nombre, anio in materias:
        if comparison_key(nombre) not in vistas:
            vistas.add(comparison_key(nombre))
            unicas.append((nombre, anio))
    return unicas


_PIE_DISENO = re.compile(r"(?i)^(\d+|\||corresponde al exp.*|(y\s+)?su agregado.*|total\b.*|if-\d{4}-[\w-]+|p[áa]gina \d+ de \d+)$")
def plan_up_dyc(html: str) -> list[tuple[str, int]]:
    """Palermo's Diseño y Comunicación plans: a block per year ("1 / er año",
    "2 / do año") of cuatrimestres, each subject a name followed by its code
    line ("020221 | 026451") and a slogan. The plan is read up to the line
    that gives the final degree ("Título Final: ..."): the tables after it
    are the completion cycles'. The page repeats the subjects of a year for
    its small screens: each name counts once a year. Its elective slots
    ("Electiva I") count as subjects."""
    soup = BeautifulSoup(html or "", "html.parser")
    for etiqueta in soup(["script", "style"]):
        etiqueta.decompose()
    lineas = [t for t in (clean_text(x) for x in soup.get_text("\n").split("\n")) if t]
    materias: list[tuple[str, int]] = []
    anio = 0
    for i, linea in enumerate(lineas):
        if re.match(r"(?i)t[ií]tulo final", linea) and materias:
            break
        if re.fullmatch(r"\d", linea) and i + 1 < len(lineas) \
                and re.match(r"(?i)(?:er|do|ro|to|mo|vo|no)\s*a[ñn]o", lineas[i + 1]):
            anio = int(linea)
        elif anio and re.match(r"(?i)trabajo final de grado", linea):
            _agregar(materias, "Trabajo Final de Grado (Proyecto de Graduación)", anio)
        elif anio and (re.fullmatch(r"(?i)electiva [ivx]+", linea)
                       # (A slot the student fills: "Cultura I" over "LIBERTAD DE ELEGIR".)
                       or (i + 1 < len(lineas) and lineas[i + 1].lower() == "libertad de elegir"
                           and len(linea) < 40)
                       or (i + 1 < len(lineas) and re.fullmatch(r"\d{5,6}(?: \| \d{5,6})*", lineas[i + 1])
                           and not re.fullmatch(r"\d{5,6}(?: \| \d{5,6})*", linea))):
            _agregar(materias, linea, anio)
    return materias


_CONECTOR_FINAL = re.compile(r"(?i)\b(y|e|de|del|la|las|los|el|en|para|con|a|al|por)$")


def _titulo_de_unidad(lineas: list[str], i: int) -> str:
    """The unit heading above line i (its "Marco orientador"): the lines
    right above it, past the page's footer; a heading wrapped over two or
    three lines is one when each line runs on into the next."""
    j = i - 1
    while j >= 0 and (not lineas[j] or _PIE_DISENO.match(lineas[j])):
        j -= 1
    bloque = []
    while j >= 0 and lineas[j] and not _PIE_DISENO.match(lineas[j]) and len(bloque) < 3:
        bloque.insert(0, lineas[j])
        j -= 1
    # Neuquén sets the unit's "Eje articulador: ..." between its heading and
    # its "Formato": the heading is what comes before it.
    eje = next((k for k, l in enumerate(bloque) if re.match(r"(?i)^eje articulador\s*:", l)), None)
    if eje:
        bloque = bloque[:eje]
    rotulo = next((k for k, l in enumerate(bloque) if re.match(r"(?i)^(?:denominaci[óo]n|unidad curricular)\s*:", l)), None)
    if rotulo is not None:  # a labelled name runs to its "Formato:"
        bloque = bloque[rotulo:]
        # ... or to the unit's next label (Mendoza: "Denominación:" over its
        # "Ubicación en el mapa curricular:" and "Régimen de cursado:").
        otro = next((k for k, l in enumerate(bloque) if k and re.match(
            r"(?i)^(?:ubicaci[óo]n|r[ée]gimen|carga horaria|formato)\b", l)), None)
        if otro:
            bloque = bloque[:otro]
    # A heading set in capitals over two lines ("TALLER DE JUEGOS Y MATERIALES"
    # / "LÚDICOS") is one.
    mayusculas = len(bloque) > 1 and all(l.isupper() for l in bloque[-2:])
    while rotulo is None and not mayusculas and len(bloque) > 1 and not (all(not l.endswith(".") for l in bloque[:-1])
                                   and all(_CONECTOR_FINAL.search(a) or b[:1].islower()
                                           for a, b in zip(bloque, bloque[1:]))):
        bloque.pop(0)
    titulo = re.sub(r"\.\s+(I{1,3})$", r" \1", " ".join(bloque).strip().rstrip(".").strip())
    if titulo.isupper():
        titulo = _ROMANO_FINAL.sub(lambda m: m.group(1).upper(), titulo[:1] + titulo[1:].lower())
    return titulo


def plan_marco_orientador(secciones: tuple[str, ...], texto: str) -> list[tuple[str, int]]:
    """A Province of Buenos Aires design of 2008–2009 (Educación Física,
    Educación Especial) that gives each unit as a heading followed by its
    "Marco orientador", under its year ("PRIMER AÑO"). The units are read
    in the sections that open with the given headings ("3/ CONTENIDOS DEL
    PROFESORADO DE EDUCACIÓN FÍSICA"; Especial's common first years and one
    orientation's), each up to the next "CONTENIDOS …" or numbered part."""
    lineas = [clean_text(l.replace("\f", "")) for l in texto.splitlines()]
    materias: list[tuple[str, int]] = []
    for seccion in secciones:
        inicio = next((i for i, l in enumerate(lineas) if re.match(seccion, l)), None)
        if inicio is None:
            return []
        anio = 0
        for i in range(inicio + 1, len(lineas)):
            linea = lineas[i]
            if re.match(r"^(CONTENIDOS\b|\d/ )", linea):
                break
            ano = re.match(r"(?i)^(primer|segundo|tercer|cuarto|quinto)\s+a[ñn]o$", linea)
            if ano:
                anio = _ANIO_INDICE[ano.group(1).lower()]
            elif anio and re.match(r"(?i)^marco orientador\s*[.:]?$", linea):
                titulo = _titulo_de_unidad(lineas, i)
                if titulo and not re.match(r"(?i)^(campos? de|herramientas? de la pr[áa]ctica)", titulo) \
                        and not titulo.endswith(":") and len(titulo.split()) <= 16:
                    materias.append((titulo, anio))
    vistas: set[str] = set()
    unicas = []
    for nombre, anio in materias:
        if comparison_key(nombre) not in vistas:
            vistas.add(comparison_key(nombre))
            unicas.append((nombre, anio))
    return unicas


def plan_formato_ubicacion(texto: str) -> list[tuple[str, int]]:
    """A Province of Buenos Aires design of 2017 on (Profesorado de Inglés;
    the Técnico Profesional ones of 2023): each unit a heading ("Pedagogía",
    or "Denominación: Pedagogía") over its "Formato:", whose "Ubicación en
    el Diseño Curricular: Campo … – Primer año" (or "1° año") a few lines
    below gives its year."""
    lineas = [clean_text(l.replace("\f", "")) for l in texto.splitlines()]
    materias: list[tuple[str, int]] = []
    for i, linea in enumerate(lineas):
        # "Formato:" (Buenos Aires), "Tipo de Unidad Curricular:" (Tucumán).
        if not re.match(r"(?i)^(?:formato(?: curricular)?|tipo de unidad curricular)\s*:", linea):
            continue
        siguientes = [l for l in lineas[i + 1:i + 30] if l and not _PIE_DISENO.match(l)][:5]
        # Mendoza: "Ubicación en el mapa curricular: 1° Año" above its "Formato"
        # (and then the one below is the next unit's).
        ubicacion = next((l for l in lineas[max(0, i - 4):i]
                          if re.match(r"(?i)^ubicaci[óo]n en el (?:mapa|dise[ñn]o) curricular\s*:", l)), "")
        ubicacion = ubicacion or next((l for l in siguientes if re.match(
            r"(?i)^ubicaci[óo]n (?:sugerida )?en (?:el )?(?:dise[ñn]o|plan de estudios?)", l)), "")
        # Neuquén: "Año: Primero".
        ordinal = next((re.match(r"(?i)^a[ñn]o\s*:\s*(primer|segund|tercer|cuart)o?\b", l) for l in siguientes
                        if re.match(r"(?i)^a[ñn]o\s*:\s*(primer|segund|tercer|cuart)o?\b", l)), None)
        if not ubicacion and ordinal:
            ubicacion = {"primer": "1", "segund": "2", "tercer": "3", "cuart": "4"}[ordinal.group(1).lower()] + " año"
        ano = re.search(r"(?i)\b(primer|segundo|tercer|cuarto|quinto|[1-5])(?:er|do|ro|to)?\.?\s*[°º]?\s*a[ñn]o\b",
                        ubicacion)
        titulo = _titulo_de_unidad(lineas, i)
        if re.match(r"(?i)^(?:r[ée]gimen|ubicaci[óo]n)\b", titulo):
            # A blank line between the unit's "Denominación:" and its other
            # labels (Mendoza): the name is the labelled line further up.
            k = next((k for k in range(i - 1, max(-1, i - 9), -1)
                      if re.match(r"(?i)^denominaci[óo]n\s*:", lineas[k])), None)
            partes = []
            # Its name may run on to the next line, up to a blank or a label.
            while k is not None and k < i and lineas[k] and (not partes or not re.match(r"(?i)^[\w ]+:\s", lineas[k])):
                partes.append(lineas[k])
                k += 1
            titulo = " ".join(partes)
        titulo = re.sub(r"(?i)^(?:denominaci[óo]n|unidad curricular)\s*:\s*", "", titulo)
        # Tucumán numbers a unit by its field and place ("F G 1. 1 - PEDAGOGÍA",
        # "FE 3.1ALFABETIZACIÓN", "FPP 4.1. PRÁCTICA ..."); its institutional
        # spaces ("EDI (ver recomendaciones temáticas)") are not units.
        titulo = re.sub(r"(?i)^f\s?(?:g|e|pp)\.?\s*\d+\s*\.\s*\d+(?:\s*,\s*\d+)*(?:\s*y\s*\d+)?\s*[.\-–]?\s*",
                        "", titulo)
        titulo = titulo[:1].upper() + titulo[1:]
        if re.match(r"(?i)^edi\b", titulo):
            continue
        # A heading numbered as the document's section ("6.2.1.3 Pedagogía")
        # or by its year ("1° AÑO PEDAGOGÍA"): the year must be the one its
        # "Ubicación" gives, or the unit is not taken.
        titulo = re.sub(r"^\d+(?:\.\d+)+\s+", "", titulo.strip())
        # Numbered in the map's order: "01 - Pensamiento Filosófico" (Mendoza).
        titulo = re.sub(r"^\d{1,2}\s*[-–.]\s*(?=\D)", "", titulo)
        prefijo = re.match(r"(?i)^([1-5])\s*[°º]\s*a[ñn]o\s+", titulo)
        if prefijo:
            titulo = titulo[prefijo.end():]
            titulo = _ROMANO_FINAL.sub(lambda m: m.group(1).upper(), titulo[:1].upper() + titulo[1:])
            if ano and (ano.group(1) if ano.group(1).isdigit() else str(_ANIO_INDICE[ano.group(1).lower()])) != prefijo.group(1):
                continue
        letras = [c for c in titulo if c.isalpha()]
        if len(letras) < 4:
            continue
        if sum(c.isupper() for c in letras) >= 0.8 * len(letras):
            titulo = _ROMANO_FINAL.sub(lambda m: m.group(1).upper(), titulo[:1] + titulo[1:].lower())
        if ano and titulo and len(titulo.split()) <= 25 and not titulo.endswith(":") \
                and not re.match(r"(?i)^(primer|segundo|tercer|cuarto|quinto)\s+a[ñn]o\b", titulo):
            clave = ano.group(1).lower()
            materias.append((titulo, int(clave) if clave.isdigit() else _ANIO_INDICE[clave]))
    vistas: set[str] = set()
    unicas = []
    for nombre, anio in materias:
        if comparison_key(nombre) not in vistas:
            vistas.add(comparison_key(nombre))
            unicas.append((nombre, anio))
    return unicas



def plan_listas_sfe(texto: str) -> list[tuple[str, int]]:
    """A Province of Santa Fe design (Profesorados de Educación Inicial and
    Primaria, Res. 528/09 and 529/09): each field lists its units by year,
    "Primer Año:" (or "… que se desarrollarán en el Primer Año de la
    carrera son:") over lines "− Pedagogía.". A unit the structure table
    marks "*" is an experimental space the Ministry says not to offer
    ("Movimiento y Cuerpo I*"), and is left out."""
    lineas = [clean_text(l.replace("\f", "")) for l in texto.splitlines()]
    no_ofrecer = {comparison_key(m.group(1)) for m in re.finditer(r"([A-ZÁÉÍÓÚ][\wáéíóúñ ]{3,60}?)\*", texto)}
    materias: list[tuple[str, int]] = []
    anio = 0
    for i, linea in enumerate(lineas):
        ano = re.match(r"(?i)^(primer|segundo|tercer|cuarto)\s+a[ñn]o\s*:?$", linea)
        cabeza = re.search(r"(?i)\b(primer|segundo|tercer|cuarto)\s+a[ñn]o\b.*\bson\s*:$",
                           (lineas[i - 1] + " " + linea) if i else linea)
        if ano or (cabeza and linea.endswith(":")):
            anio = _ANIO_INDICE[(ano or cabeza).group(1).lower()]
            continue
        item = re.match(r"^[−–-]\s+(.+?)\.?$", linea)
        if anio and item:
            nombre = item.group(1).strip()
            if not re.fullmatch(r"[\d\s-]+", nombre) and comparison_key(nombre) not in no_ofrecer \
                    and not nombre.endswith(",") and len(nombre.split()) <= 12:
                materias.append((nombre, anio))
        elif linea and not item:
            anio = 0
    vistas: set[str] = set()
    unicas = []
    for nombre, anio_ in materias:
        if comparison_key(nombre) not in vistas:
            vistas.add(comparison_key(nombre))
            unicas.append((nombre, anio_))
    return unicas


_ROMANO_FINAL = re.compile(r"\b(i{1,3}|iv|v)\b(?=[:\s.]|$)")


def plan_codigos_salta(texto: str) -> list[tuple[str, int]]:
    """A Province of Salta design (Profesorados de Educación Inicial and
    Primaria, Res. 537 and 538 of 2009): its index lists each unit under
    "9. CAMPOS DE LA FORMACIÓN" with a code whose first figure is its year
    ("2.13 PEDAGOGÍA ..... 88"); a name the index wraps runs on to the line
    that ends in its page. The plan's table ("2.13 Materia Pedagogía 5")
    gives the same names in their own case, and the units the index leaves
    out. The elective slot ("Propuesta variable o complementaria") is not a
    unit."""
    lineas = [clean_text(l.replace("\f", "")) for l in texto.splitlines()]
    inicio = next((i for i, l in enumerate(lineas) if re.match(r"^9\.\s*CAMPOS DE LA FORMACI[ÓO]N\b.*\.{3,}", l)), None)
    if inicio is None:
        return []
    fin = next((i for i in range(inicio + 1, len(lineas)) if re.match(r"^1\d\.\s", lineas[i])), len(lineas))
    indice: dict[str, str] = {}
    i = inicio + 1
    while i < fin:
        codigo = re.match(r"^([1-5]\.\d{2})\s+(.+)$", lineas[i])
        if codigo:
            nombre = codigo.group(2)
            if not re.search(r"\.{3,}\s*\d*$", nombre) and i + 1 < fin and lineas[i + 1] \
                    and not re.match(r"^[1-5]\.\d{2}\s|^\d\.\d\s", lineas[i + 1]) and lineas[i + 1].isupper():
                nombre += " " + lineas[i + 1]
                i += 1
            nombre = re.sub(r"[\s.…]*\d*$", "", nombre).strip().rstrip("*").strip()
            letras = [c for c in nombre if c.isalpha()]
            if letras and sum(c.isupper() for c in letras) >= 0.8 * len(letras):
                nombre = _ROMANO_FINAL.sub(lambda m: m.group(1).upper(), nombre[:1] + nombre[1:].lower())
            indice.setdefault(codigo.group(1), nombre)
        i += 1
    tabla: dict[str, str] = {}
    for linea in lineas[fin:]:
        fila = re.match(r"^([1-5]\.\d{2})\s+(?:Materia|Taller|Seminario(?:\s*-?\s*Taller)?|Semin\.?-?|Trabajo)\s+"
                        r"(.+?)\**\s+\d+\**(?:\s+\d+)*$", linea)
        if fila and not _CONECTOR_FINAL.search(fila.group(2)) and not fila.group(2).endswith(":"):
            tabla.setdefault(fila.group(1), fila.group(2).strip().rstrip("*").strip())
    materias = []
    for codigo in sorted(set(indice) | set(tabla), key=lambda c: (int(c[0]), c)):
        nombre = indice.get(codigo)
        propia = tabla.get(codigo)
        if propia and (nombre is None or comparison_key(propia) == comparison_key(nombre)):
            nombre = propia
        if nombre and not re.match(r"(?i)^propuesta variable", nombre):
            materias.append((nombre, int(codigo[0])))
    vistas: set[str] = set()
    unicas = []
    for nombre, anio in materias:
        if comparison_key(nombre) not in vistas:
            vistas.add(comparison_key(nombre))
            unicas.append((nombre, anio))
    return unicas


def plan_estructura_jujuy(texto: str) -> list[tuple[str, int]]:
    """Jujuy's designs (Profesorado de Educación Primaria): an "ESTRUCTURA
    CURRICULAR" table of numbered units ("7  Esp  <name>  Taller  4"), each
    year closed by its "TOTAL HORAS 1º AÑO". A unit whose name the table set
    over two lines leaves its own row without one: the name is the line
    above it and the line below it ("Problemática Contemporánea de la" /
    "Educación Primaria"). The institution's optional spaces ("Opción
    Institucional I") are not units of the plan."""
    lineas = texto.replace("\f", "\n").splitlines()
    inicio = next((i for i, l in enumerate(lineas) if re.search(r"ESTRUCTURA CURRICULAR", l)), None)
    cabecera = next((i for i in range(inicio or 0, len(lineas)) if "UNIDAD CURRICULAR" in lineas[i] and "Formato" in lineas[i]), None)
    if inicio is None or cabecera is None:
        return []
    x_nombre = lineas[cabecera].index("UNIDAD CURRICULAR") - 18
    x_formato = lineas[cabecera].index("Formato") - 2
    fila = re.compile(r"^\s*(\d{1,2})\s+(?:Gral|Esp|P\s*Prof)?\b")

    def nombre_en(linea: str) -> str:
        parte = linea[x_nombre:x_formato] if len(linea) > x_nombre else ""
        parte = re.sub(r"^\s*(?:\d{1,2}\s+)?(?:Gral|Esp|P\s*Prof|Prof)\b", "", parte)
        parte = re.sub(r"\s{2,}\d+\s*$", "", parte)
        return clean_text(parte)

    unidades: list[list[Any]] = []
    pendientes: list[list[Any]] = []
    usadas: set[int] = set()
    materias: list[tuple[str, int]] = []
    for i in range(cabecera + 1, len(lineas)):
        linea = lineas[i]
        total = re.search(r"TOTAL HORAS\s+(\d)\s*[º°]?\s*A[ÑN]O", linea)
        if total:
            for u in pendientes:
                if u[1] and not re.match(r"(?i)opci[óo]n institucional", u[1]):
                    materias.append((u[1], int(total.group(1))))
            pendientes = []
            if total.group(1) == "4" or not any(fila.match(l) for l in lineas[i + 1:i + 30]):
                break
            continue
        if fila.match(linea):
            propio = nombre_en(linea)
            if not propio:
                # Each piece of a wrapped name belongs to one row only.
                arriba = next((j for j in range(i - 1, max(i - 3, cabecera), -1)
                               if fila.match(lineas[j]) or (j not in usadas and nombre_en(lineas[j]))), None)
                abajo = next((j for j in range(i + 1, min(i + 4, len(lineas)))
                              if fila.match(lineas[j]) or "TOTAL" in lineas[j]
                              or (j not in usadas and nombre_en(lineas[j]))), None)
                partes = []
                for j in (arriba, abajo):
                    if j is not None and not fila.match(lineas[j]) and "TOTAL" not in lineas[j]:
                        partes.append(nombre_en(lineas[j]))
                        usadas.add(j)
                propio = clean_text(" ".join(partes))
            unidad = [int(fila.match(linea).group(1)), propio]
            unidades.append(unidad)
            pendientes.append(unidad)
    return materias


def plan_ungs(html: str) -> list[tuple[str, int]]:
    """UNGS: the plan's table has every subject and no year; the career's
    itinerary (on the same page, under "Itinerario") lays the subjects out by
    semester, a number in a heading beside a list (semesters 1 to 3 the first
    year, see below). The itinerary for a student starting in the first semester is
    the one read; the one starting in the second shifts every subject by a
    term. Where a page has two itineraries (an old plan and the current one),
    the first is the current."""
    soup = BeautifulSoup(html or "", "html.parser")
    tablas = soup.find_all("table")
    # Some careers publish only the itinerary for a student starting in the
    # second semester (Sistemas de Información Geográfica): its semester 1 is
    # the second half of the first year.
    for patron in (r"(?i)iniciando la carrera en el primer", r"(?i)iniciando la carrera en el segundo"):
        materias: list[tuple[str, int]] = []
        for tabla in tablas:
            if not re.search(patron, _texto(tabla)):
                continue
            for fila in tabla.find_all("tr"):
                celdas = fila.find_all("td")
                for i, celda in enumerate(celdas):
                    numero = re.fullmatch(r"\d{1,2}", _texto(celda.find(["h1", "h2", "h3", "h4"])))
                    if not numero or i + 1 >= len(celdas):
                        continue
                    # The first semester is the initial workshops: a five-year
                    # degree runs to an eleventh, a three-year tecnicatura to a
                    # seventh. Semesters 1 to 3 are the first year, then two a
                    # year, whichever half of the year the student starts in.
                    anio = max(1, int(numero.group(0)) // 2)
                    for item in celdas[i + 1].find_all("li"):
                        # Several subjects in one item, one per line:
                        # "Taller de Radio I<br/>Planificación y evaluación…"
                        # (Comunicación).
                        # A name wrapped at a line break ("…Sistemas de<br/>Información
                        # Geográfica", Ecología) goes on after a word that
                        # cannot end it, or into a line in lower case.
                        nombres: list[str] = []
                        for linea in item.get_text("\n").split("\n"):
                            linea = clean_text(linea).strip()
                            if not linea:
                                continue
                            if nombres and (re.search(r"(?i)\b(de|del|la|las|los|el|y|e|en|a|con|para|por)$", nombres[-1])
                                            or linea[:1].islower()):
                                nombres[-1] += " " + linea
                            else:
                                nombres.append(linea)
                        for nombre in nombres:
                            _agregar(materias, nombre, anio)
            break
        if materias:
            return desde_el_primero(materias)
    # A page without an itinerary (Sociología): its plan's table, the first
    # headed "Asignaturas" (not the pool of electives, which says each one's
    # "Modalidad"), every subject without its year.
    for tabla in tablas:
        filas = tabla.find_all("tr")
        encabezado = [_texto(c) for c in filas[0].find_all(["td", "th"])] if filas else []
        if not encabezado or encabezado[0] != "Asignaturas" or "Modalidad" in encabezado:
            continue
        leidas: list[tuple[str, int]] = []
        for fila in filas[1:]:
            celdas = fila.find_all(["td", "th"])
            if celdas and _texto(celdas[0]):
                # (_agregar keeps only a subject with its year: one for all, then none.)
                _agregar(leidas, _texto(celdas[0]), 1)
        return [(nombre, None) for nombre, _ in leidas]  # type: ignore[misc]
    return []


def plan_forestales_unam(html: str) -> list[tuple[str, int]]:
    """UNaM Forestales: one table, each year a row of its own ("PRIMER AÑO:")
    over the rows of its subjects, each its number, its name and its term
    ("5 | Introducción a las Ciencias Forestales | 1º Cuatr."). A row without
    a number is not in the sequence ("MI | Módulo Introductorio", the
    entrance course)."""
    soup = BeautifulSoup(html or "", "html.parser")
    materias: list[tuple[str, int]] = []
    for tabla in soup.find_all("table"):
        anio = None
        for fila in tabla.find_all("tr"):
            celdas = [_texto(c) for c in fila.find_all(["td", "th"])]
            llenas = [c for c in celdas if c]
            if len(llenas) == 1 and anio_de(llenas[0]):
                anio = anio_de(llenas[0])
            elif anio and len(celdas) >= 2 and re.fullmatch(r"\d{1,2}", celdas[0]) and celdas[1]:
                _agregar(materias, celdas[1], anio)
        if materias:
            break
    return desde_el_primero(materias)


_FILA_UNPAZ = re.compile(r"^(\s*)(\d{2}|\d{4})\s{2,}(\S.*?)(?:\s{2,}(?:Anual|Cuatrimestral|Bimestral|Semestral|Trimestral)\b.*)?$")


def plan_unpaz(texto: str) -> list[tuple[str, int]]:
    """UNPAZ's career brochures (``pdftotext -layout``): one table per year,
    each under its header ("Código  Asignatura  Régimen  Horas  Correlatividad")
    with the year's name beside it ("Primer año", wherever the table's
    middle falls, or just over the header), each subject its code (two digits, or four: "6001"),
    its name and its term; a name too long for its cell goes on in the line
    right below, at the name's column ("Introducción a los Procedimientos" /
    "de Quirófano"). The options of an elective slot ("35 Optativa 1" over
    "OP1. 1 – ...") are not the sequence: the slot is. The degree's lines
    ("Título intermedio", "Título") close a table. A table whose year is not
    named, or named twice, makes the plan unreadable."""
    lineas = [l for l in texto.splitlines() if l.strip() and l.strip().lower() not in {"horas", "semanales"}]
    bloques: list[dict] = []
    actual: dict | None = None
    pendiente: int | None = None
    seguida = False
    for numero, linea in enumerate(lineas):
        limpia = linea.strip()
        if re.search(r"C[óo]digo\s+Asignatura", linea):
            # The year may head the header's own line ("Tercer año   Código   Asignatura").
            delante = re.match(r"(?i)(primer|segundo|tercer|cuarto|quinto|sexto)\s+a[ñn]o\s+C[óo]digo", limpia)
            if delante:
                pendiente = _ORDINALES[delante.group(1).lower()]
            actual = {"anios": set() if pendiente is None else {pendiente}, "filas": []}
            bloques.append(actual)
            pendiente, seguida = None, False
            continue
        nombre_del_anio = re.match(r"(?i)(primer|segundo|tercer|cuarto|quinto|sexto)\s+a[ñn]o\b", limpia)
        if nombre_del_anio:
            anio = _ORDINALES[nombre_del_anio.group(1).lower()]
            # Just over the next table's header: that table's year.
            if numero + 1 < len(lineas) and re.search(r"C[óo]digo\s+Asignatura", lineas[numero + 1]):
                pendiente = anio
                continue
            if actual is not None:
                actual["anios"].add(anio)
            resto = limpia[nombre_del_anio.end():]
            if not resto.strip():
                continue
            linea = " " * (len(linea) - len(resto)) + resto
            limpia = linea.strip()
        if actual is None:
            continue
        if re.match(r"(?i)t[íi]tulo\b", limpia):
            actual, seguida = None, False
            continue
        fila = _FILA_UNPAZ.match(linea)
        if fila:
            nombre = re.split(r"\s{2,}", fila.group(3).strip())[0]
            actual["filas"].append([len(fila.group(1)) + len(fila.group(2)), nombre])
            seguida = True
            continue
        # The rest of a name, right below it at its column; a stray
        # prerequisite far right ("producción audiovisual I      -") is not
        # part of it.
        sangria = len(linea) - len(linea.lstrip())
        limpia = re.sub(r"\s{2,}[\d\s-]+$", "", limpia)
        if (seguida and re.match(r"[A-Za-zÁÉÍÓÚÑáéíóúñ(]", limpia)
                and actual["filas"][-1][0] < sangria <= actual["filas"][-1][0] + 12
                and not re.search(r"\s{2,}", limpia)):
            actual["filas"][-1][1] += " " + limpia
            continue
        seguida = False
    materias: list[tuple[str, int]] = []
    for bloque in bloques:
        if not bloque["filas"]:
            continue
        if len(bloque["anios"]) != 1:
            return []
        anio = next(iter(bloque["anios"]))
        for _, nombre in bloque["filas"]:
            _agregar(materias, nombre, anio)
    return desde_el_primero(materias)


_ANIO_UNSO = re.compile(r"(?i)^(primer|segundo|tercer|cuarto|quinto|sexto)\s+a[ñn]o\b")
# The table's head, repeated on each page: its columns' words.
_CABEZA_UNSO = {"asignatura", "asignaturas", "horas", "hora", "hs", "de", "del", "totales", "teóricas", "teoricas",
                "prácticas", "practicas", "régimen", "regimen", "carga", "horaria", "total", "interacción",
                "pedagógica", "trabajo", "autónomo", "estudiante", "créditos", "pre", "profesionales", "modalidad"}
_TRAMO_UNSO = re.compile(r"(?i)^(?:(?:primer|segundo)\s+cuatrimestre|anual|subtotal\b.*)$")
# What closes a year: its total, the degree it gives ("TITULO INTERMEDIO  1184 ..."),
# or a term's heading with figures, the total mislabelled (Psicopedagogía:
# "SEGUNDO CUATRIMESTRE  720  418  302").
_CIERRE_UNSO = re.compile(r"(?i)^(?:total|subtotal anual)\b|^(?:t[íi]tulo\b.*|(?:primer|segundo) cuatrimestre)\s\d+(?:\s\d+)*$")
_FIN_UNSO = re.compile(r"(?i)^(?:carga horaria total|total (?:de horas|carrera)|anexo|correlatividades$)")
_HORAS_UNSO = re.compile(r"^(\s*)(?:(\S.*?)(?:\s{2,}(?:Cuatrimestral|Anual|Bimestral))?\s{2,})?(\d+(?:\s+\d+)*)\s*$")


def plan_unso(texto: str) -> list[tuple[str, int]]:
    """UNSO's plans (``pdftotext -layout``): a table per year ("PRIMER AÑO",
    then "PRIMER CUATRIMESTRE"), a subject per row with its hours to the
    right ("Física   64   32   32", or its term before them: "Costos
    Cuatrimestral 64"), the rows mostly apart by a blank line. A name too
    long for its cell takes two lines, the hours on the first, the second or
    a line of their own between them ("Taller de búsqueda Jurídica y
    análisis" / "64 16 48" / "Jurisprudencial"); where the rows are not
    apart, a line without hours goes with the row below it, unless it goes
    on in small letters ("en Cs. Sociales") or ends the group. A number at
    the names' column is the name's ("Postproducción Audiovisual" / "1   64
    32 32"); one at the hours' column below a row with hours fell from it
    ("Legales y comerciales  36  12" / "48"). A total closes the year
    ("TOTAL ANUAL", "TOTAL", the degree's line); what follows it without a
    year of its own (the supervised practice, the final project) is not in
    a year and is left out, unless a subtotal comes after it (a total out
    of place: the Criminalística plan). The annex (prerequisites) is not the
    plan."""
    lineas = texto.replace("\f", "\n").splitlines()

    def fila_de(linea: str) -> tuple[str | None, int] | None:
        # A row's name and where its hours begin; a name of figures alone
        # is a number of the hours ("64   186   250"), or of the name.
        fila = _HORAS_UNSO.match(linea)
        if not fila:
            return None
        if fila.group(2) and not fila.group(2).isdigit():
            return fila.group(2), fila.start(3)
        return (fila.group(2), fila.start(2)) if fila.group(2) else (None, fila.start(3))

    # Where the hours begin: the leftmost hours of a row with its name.
    columna = min((f[1] for f in map(fila_de, lineas) if f and f[0] and not f[0].isdigit()), default=0)
    materias: list[tuple[str, int]] = []
    anio: int | None = None
    cerrado: int | None = None
    sueltas: list[str] = []
    bloque: list[str] = []

    def resolver() -> bool:
        partes: list[list] = []  # [name, has hours]
        for linea in bloque:
            fila = fila_de(linea)
            if fila and fila[0] and fila[0].isdigit():
                if fila[1] < columna - 8:
                    partes.append([fila[0], True])  # a number at the names' column: "1   64  32  32"
                    continue
                fila = (None, fila[1])
            if fila and fila[0] is None and partes and partes[-1][1]:
                continue  # a number of the row above, fallen below it
            nombre = (fila[0] or "") if fila else re.sub(r"\s{2,}(?:Cuatrimestral|Anual)\s*$", "", linea)
            partes.append([re.sub(r"\s+", " ", nombre.strip()), bool(fila)])
        bloque.clear()
        # Figures alone: a subtotal's, its word on the line below ("288  152  136" / "SUBTOTAL").
        if not any(nombre for nombre, _ in partes) or (anio is None and (cerrado is None or not any(h for _, h in partes))):
            return True
        nombres: list[str] = []
        pendiente: list[str] = []
        for numero, (nombre, horas) in enumerate(partes):
            if not horas:
                # The rest of the row just above: in small letters, or the group's last line.
                if (nombres and not pendiente and partes[numero - 1][1]
                        and (numero == len(partes) - 1 or re.match(r"[a-záéíóúñ(\d]", nombre))):
                    nombres[-1] += " " + nombre
                else:
                    pendiente.append(nombre)
                continue
            nombres.append(" ".join(pendiente + ([nombre] if nombre else [])))
            pendiente = []
        if pendiente or not all(nombres):
            return False
        for nombre in nombres:
            # A word the cell broke: "Georreferencia-" / "ción".
            nombre = re.sub(r"([^\W\d_])- (?=[a-záéíóúñ])", r"\1", nombre)
            if anio is not None:
                _agregar(materias, nombre, anio)
            else:
                sueltas.append(nombre)
        return True

    for linea in lineas:
        limpia = re.sub(r"\s+", " ", linea.strip())
        if not limpia or re.fullmatch(r"\d+/\d+", limpia):
            if not resolver():
                return []
            continue
        if _FIN_UNSO.search(limpia):
            break
        del_anio = _ANIO_UNSO.match(limpia)
        cabeza = not re.search(r"\d", limpia) and set(re.findall(r"[^\W\d_]+", limpia.lower())) <= _CABEZA_UNSO
        if del_anio or cabeza or _TRAMO_UNSO.match(limpia) or _CIERRE_UNSO.match(limpia):
            if not resolver():
                return []
            if del_anio:
                anio, cerrado = _ORDINALES[del_anio.group(1).lower()], None
                sueltas.clear()
            elif _CIERRE_UNSO.match(limpia):
                if anio is not None:
                    anio, cerrado = None, anio
            elif re.match(r"(?i)^subtotal\b", limpia) and cerrado is not None and sueltas:
                # A subtotal after the total: the rows between were the year's.
                for nombre in sueltas:
                    _agregar(materias, nombre, cerrado)
                sueltas.clear()
                anio, cerrado = cerrado, None
            continue
        bloque.append(linea)
    if not resolver():
        return []
    return desde_el_primero(materias)


def plan_fmed_uba(texto: str) -> list[tuple[str, int]]:
    """UBA, Medicina: the plan PDF as ``pdftotext -layout`` gives it, the
    years headed "* 2° AÑO *", each subject numbered at the left margin
    ("7. Fisiología   Cuatrimestral ...") and its name wrapped on the lines
    below it until a blank line or the next number. The other columns (how
    long it runs, its prerequisites) are cut at the first wide gap; "(Se
    realiza en el CBC)" says where, not what."""
    materias: list[tuple[str, int]] = []
    anio: int | None = None
    actual: list[str] = []

    def cerrar() -> None:
        if actual and anio:
            nombre = re.sub(r"\s*\(se realiza en el cbc\)", "", " ".join(actual), flags=re.I)
            _agregar(materias, nombre, anio)
        actual.clear()

    for linea in (texto or "").splitlines():
        encabezado = re.search(r"\*\s*(\d)\s*[°º]?\s*AÑO\s*\*", linea, re.I)
        if encabezado:
            cerrar()
            anio = int(encabezado.group(1))
            continue
        izquierda = re.split(r"\s{3,}", linea.strip())[0] if linea.strip() else ""
        numero = re.match(r"^(\d{1,2})\.\s+(\S.*)$", linea) if not linea.startswith(" ") else None
        if numero:
            cerrar()
            actual.append(re.split(r"\s{3,}", numero.group(2))[0])
        elif not linea.strip():
            cerrar()
        elif actual and not linea.startswith(" ") and not re.search(r"(?i)cuatrimestre|aprobad|regular", izquierda):
            actual.append(izquierda)
    cerrar()
    return desde_el_primero(materias)


plan_fmed_uba.respaldo = True  # its other layouts go to the general reader


def plan_uno(ruta: str) -> list[tuple[str, int]]:
    """UNO's plan PDFs, read as pdfplumber's tables: each subject a row with
    its term of study ("Cuatrimestral", "Anual"), and three cells on the
    term it is taken in, counted from the start ("5", "5-6": the fifth and
    sixth, the third year). Its name is the cell before the term of study
    (a wrapped name comes whole). A subject row without its term counted
    makes the plan unreadable."""
    import pdfplumber

    materias: list[tuple[str, int]] = []
    with pdfplumber.open(ruta) as pdf:
        for pagina in pdf.pages:
            for tabla in pagina.extract_tables():
                for fila in tabla:
                    celdas = [" ".join((c or "").split()) for c in fila]
                    regimen = next((i for i, c in enumerate(celdas)
                                    if re.fullmatch(r"(?i)cuatrimestral|anual|semestral|bimestral", c)), None)
                    if regimen is None or regimen == 0 or not celdas[regimen - 1]:
                        continue
                    termino = celdas[regimen + 3] if regimen + 3 < len(celdas) else ""
                    contado = re.fullmatch(r"(\d{1,2})(?:\s*-\s*\d{1,2})?", termino)
                    if not contado:
                        return []
                    _agregar(materias, celdas[regimen - 1], (int(contado.group(1)) + 1) // 2)
    return desde_el_primero(materias)


plan_uno.ruta = True


# "1º AÑO", "Primer Año -Ciclo Inicial-", "CICLO I - 1º AÑO": a year's heading, a line of its own.
_ANIO_UNO = re.compile(r"(?i)^(?:ciclo [\wíé ]+?\s*[-–]\s*)?(?:(primer|segundo|tercer|cuarto|quinto|sexto)\s+a[ñn]o"
                       r"|(\d)\s*[º°]\s*a[ñn]o)(?:\s*-\s*ciclo [\wíé]+\s*-)?$")
# A row's code: "02069", "02-001", "02 001", "-----------" (an elective's).
_CODIGO_UNO = re.compile(r"\d{4,5}|\d{2}-\d{2,3}|-{3,}")
# Lines in the name's column that are not a subject's: the year's hours, the
# intermediate title ("Título obtenido: ANALISTA ..."), a layer laid over
# the table ("CICLO INICIAL  Hs  2432").
# An elective's slot, a row without a code.
_ELECTIVA_UNO = re.compile(r"(?i)(?:electiva|optativa)(?: [IVX\d]+)?")
_NO_ES_FILA_UNO = re.compile(r"(?i)^(?:sub)?total\b|^horas totales$|^certificaci[óo]n\b|^plan de estudios$|^t[íi]tulo\b"
                             r"|carga horaria total|^ciclo inicial$|^obtenido:|^[\d\s*°º/–-]+$|^c$")


def plan_uno_codigos(cajas: str) -> list[tuple[str, int]]:
    """UNO's plan PDFs whose table has a code per row (``-bbox-layout``):
    "CÓDIGO  ASIGNATURA" (or "MATERIA") under "1º AÑO" / "Primer Año"
    headings. A name too long for its cell wraps above, beside and below its
    code's line ("Teoría de Grupo e Intervención" / "03084 Comunitaria";
    "Acceso a la Justicia y a los Derechos" / "02080" / "en Contexto de
    Vulnerabilidad"), so each line of the name's column is the nearest
    code's; a line about as near two codes, or far from all of them inside
    the table, gives nothing. The column right of the names has one value per
    row (its "c", "1°" or hours): a row without its code (Redes' "Electiva")
    would join the row above, so a count that differs gives nothing. Notes
    above or below the table are not read."""
    materias: list[tuple[str, int]] = []
    anio = None
    for contenido in re.findall(r"<page\b.*?</page>", cajas or "", re.S):
        palabras = [(float(x0), float(y0), float(x1), float(y1), clean_text(unescape(t)))
                    for x0, y0, x1, y1, t in _PALABRA_CON_CAJA.findall(contenido)]
        renglones: dict[int, list[tuple[float, str]]] = {}
        for x0, y0, x1, y1, t in palabras:
            renglones.setdefault(round((y0 + y1) / 2), []).append((x0, t))
        titulos = []
        for y, renglon in sorted(renglones.items()):
            titulo = _ANIO_UNO.match(" ".join(t for _, t in sorted(renglon)))
            if titulo:
                titulos.append((y, _ORDINALES[titulo.group(1).lower()] if titulo.group(1) else int(titulo.group(2))))
        cabeza = next(((x0, x1, (y0 + y1) / 2) for x0, y0, x1, y1, t in palabras if t in ("ASIGNATURA", "MATERIA")), None)
        if cabeza is None:
            # (A year's heading on a page with no table: a layout this does not read.)
            if titulos:
                return []
            continue
        hx0, hx1, hy = cabeza
        siguiente = min(((x0, x1) for x0, y0, x1, y1, t in palabras
                         if abs((y0 + y1) / 2 - hy) < 8 and x0 > hx1 and t.isupper()), default=None)
        if siguiente is None:
            return []
        # The codes, left of the names ("02 001" is two words).
        izquierda_de: dict[int, list[tuple[float, float, str]]] = {}
        for x0, y0, x1, y1, t in palabras:
            if x1 < hx0 and y0 > hy - 15:
                izquierda_de.setdefault(round((y0 + y1) / 2), []).append((x0, x1, t))
        filas = []
        for y, renglon in sorted(izquierda_de.items()):
            renglon.sort()
            if re.search(r"(?<!\d)\d{2} \d{3}(?!\d)", " ".join(t for _, _, t in renglon)):
                filas.append((y, max(x1 for _, x1, _ in renglon)))
                continue
            codigos = [x1 for _, x1, t in renglon if _CODIGO_UNO.fullmatch(t)]
            if codigos:
                filas.append((y, codigos[-1]))
        if not filas:
            continue
        izquierda = max(x for _, x in filas) + 1
        # An elective's slot has no code ("Electiva", "Optativa I" in Redes):
        # a row of its own when its line has its value beside it, near the
        # coded rows. It is not a subject (``_agregar`` leaves it out).
        for y, renglon in renglones.items():
            nombre = [(x0, t) for x0, t in renglon if izquierda < x0 < siguiente[0] - 1]
            if (_ELECTIVA_UNO.fullmatch(" ".join(t for _, t in sorted(nombre)))
                    and any(siguiente[0] - 8 <= x0 <= siguiente[1] + 8 for x0, _ in renglon)
                    and 4 < min(abs(y - fy) for fy, _ in filas) < 30 and y > hy):
                filas.append((y, izquierda - 1))
        filas.sort()
        arriba, abajo = filas[0][0] - 16, filas[-1][0] + 16
        valores = sorted((y0 + y1) / 2 for x0, y0, x1, y1, t in palabras
                         if siguiente[0] - 8 <= (x0 + x1) / 2 <= siguiente[1] + 8 and arriba <= (y0 + y1) / 2 <= abajo
                         and re.fullmatch(r"\d+[°º*]?|[cx]|Anual|Semestral|Cuatrimestr(?:e|al)", t))
        # (One row's "1º Cuatrimestre" is one value; a year's "2º AÑO" over the column is none.)
        valores = [v for v in valores if all(abs(v - ty) > 3 for ty, _ in titulos)]
        valores = [v for i, v in enumerate(valores) if i == 0 or v - valores[i - 1] > 4]
        if (len(valores) != len(filas)
                or len({min(range(len(filas)), key=lambda i: abs(filas[i][0] - v)) for v in valores}) != len(filas)):
            return []
        lineas: dict[int, list[tuple[float, str]]] = {}
        for x0, y0, x1, y1, t in palabras:
            # (A term's "1º" that reaches into the name's column is not the name's.)
            if x0 > izquierda and x1 < siguiente[0] - 1 and (y0 + y1) / 2 > hy + 5 and not re.fullmatch(r"\d+[°º]", t):
                lineas.setdefault(round((y0 + y1) / 2), []).append((x0, t))
        juntas: list[tuple[int, list[tuple[float, str]]]] = []
        for y in sorted(lineas):
            if juntas and y - juntas[-1][0] < 2.5:
                juntas[-1][1].extend(lineas[y])
            else:
                juntas.append((y, list(lineas[y])))
        partes: list[list[tuple[int, str]]] = [[] for _ in filas]
        for y, linea in juntas:
            texto = " ".join(t for _, t in sorted(linea))
            if not arriba <= y <= abajo or _ANIO_UNO.match(texto) or _NO_ES_FILA_UNO.search(texto):
                continue
            cerca = sorted((abs(y - fy), i) for i, (fy, _) in enumerate(filas))
            if cerca[0][0] > 16:
                # (A note between a year's last row and the next year's table.)
                previa = max((fy for fy, _ in filas if fy < y), default=-1)
                if any(previa < ty < y for ty, _ in titulos):
                    continue
                return []
            if len(cerca) > 1 and cerca[0][0] > 0.6 * cerca[1][0]:
                return []
            partes[cerca[0][1]].append((y, texto))
        for (fy, _), parte in zip(filas, partes):
            anio_de_la_fila = next((a for ty, a in reversed(titulos) if ty < fy), anio)
            if anio_de_la_fila is None or not parte:
                return []
            _agregar(materias, " ".join(t for _, t in sorted(parte)), anio_de_la_fila)
        if titulos:
            anio = titulos[-1][1]
    return desde_el_primero(materias)


plan_uno_codigos.cajas = True  # type: ignore[attr-defined]


def plan_uno_todos(ruta: str) -> list[tuple[str, int]]:
    """UNO: the tables pdfplumber reads whole (Matemática), then the coded
    rows by position."""
    import subprocess

    return plan_uno(ruta) or plan_uno_codigos(
        subprocess.run(["pdftotext", "-bbox-layout", ruta, "-"], capture_output=True, text=True, timeout=60).stdout)


plan_uno_todos.ruta = True


def plan_eco_unrc(ruta: str) -> list[tuple[str, int]]:
    """UNRC Económicas: its current plans are PDFs of minimum contents (its
    pages still list the old plan, "No vigente"), read as pdfplumber's
    tables: a row per subject, the year and term in the first cell of the
    term's first row ("1° año- 2° cuatrimestre"), the name in capitals
    ("SISTEMAS DE INFORMACIÓN CONTABLE I"), its contents in mixed case. A
    row of contents alone goes on from the subject above."""
    import pdfplumber

    materias: list[tuple[str, int]] = []
    anio = None
    with pdfplumber.open(ruta) as pdf:
        for pagina in pdf.pages:
            for tabla in pagina.extract_tables():
                for fila in tabla:
                    celdas = [" ".join((c or "").split()) for c in fila]
                    for celda in celdas:
                        nuevo = re.match(r"(\d)\s*[°º]\s*a[ñn]o\b", celda, re.I)
                        if nuevo:
                            anio = int(nuevo.group(1))
                    nombre = next((c for c in celdas if c and c.isupper() and re.search(r"[A-ZÁÉÍÓÚÑ]{3}", c)
                                   and not re.match(r"(?i)\d\s*[°º]\s*a[ñn]o|materia$|contenidos", c)), None)
                    if nombre and anio:
                        _agregar(materias, nombre, anio)
    return desde_el_primero(materias)


plan_eco_unrc.ruta = True


def plan_fcf_unse(html: str) -> list[tuple[str, int]]:
    """UNSE Forestales: the career's curriculum tab, a heading per year
    ("Primer Año") over its subjects, each its code and name ("57 Botánica
    Forestal"); a subject given in two halves ("Taller I: ... (1º Parte)",
    "(2º Parte)") is one. The elective slots have no code ("Asignatura
    Optativa I (IF)") and the pool after "Optativas" is not the plan."""
    soup = BeautifulSoup(html or "", "html.parser")
    for parte in soup(["script", "style"]):
        parte.decompose()
    materias: list[tuple[str, int]] = []
    anio = None
    for linea in soup.get_text("\n").split("\n"):
        linea = clean_text(linea).replace("\xa0", " ").strip()
        if not linea:
            continue
        nuevo = anio_de(linea)
        if nuevo:
            if materias and nuevo <= max(a for _, a in materias):
                break  # the same plan again, further down the page
            anio = nuevo
            continue
        if anio and re.match(r"(?i)^optativas?$|^×$", linea):
            break
        fila = re.match(r"^\d{1,3}\s+(\S.*)$", linea)
        if anio and fila:
            nombre = re.sub(r"(?i)\s*\(\s*\d\s*[°º]?\s*parte\s*\)\s*$", "", fila.group(1)).rstrip(" .")
            if all(nombre.lower() != m.lower() for m, _ in materias):
                _agregar(materias, nombre, anio)
    return desde_el_primero(materias)


_FILA_UNAHUR_2025 = re.compile(r"^\s*(\d{1,2})(?:\s+(\S.*?))?\s{2,}(?:C|A|Anual|Cuatrimestral|Bimestral)\s+(?:C[A-Z]{1,3}\s+)?\d")
_DATOS_UNAHUR_2025 = re.compile(r"^\s*(\D\S.*?)\s{2,}(?:C|A|Anual|Cuatrimestral|Bimestral)\s+(?:C[A-Z]{1,3}\s+)?\d")
_RUIDO_UNAHUR = re.compile(r"ANIVERSARIO|^\d{1,6}$")
_SIGUE = re.compile(r"(?i)\b(de|del|la|las|los|el|y|e|en|para|a|al|con|por)$")


def plan_unahur_2025(texto: str) -> list[tuple[str, int]]:
    """UNAHUR's plan resolutions from 2025 on (``pdftotext -layout``): a
    table per title ("UNIDAD CURRICULAR  D  CP  IPS ..."), the intermediate
    title's first when there is one (a part of the plan: its numbers skip
    the subjects it leaves out) and the degree's last; a heading per year
    ("PRIMER AÑO", "1° Año"), each subject its number, name and length
    ("C"). A name too long for its cell is centred on its row: it starts in
    the line above ("Laboratorio de Análisis de Alimentos," / "15
    Medicamentos y Cosméticos") and may go on in the line below ("1  C 4
    64" between "Introducción a la Salud" and "Comunitaria"); the row's
    data can also sit beside the first part, the number beside the rest
    ("Cultura y alfabetización digital en la  C CFC 2" / "5 universidad").
    The table read is the last one numbered from 1 without a gap."""
    tablas: list[list[dict]] = []
    filas: list[dict] | None = None
    anio = None
    suelta = ""
    for linea in texto.splitlines():
        limpia = clean_text(linea)
        if not limpia or _RUIDO_UNAHUR.search(limpia):
            continue
        if re.search(r"(?i)unidad curricular", limpia) and len(limpia) < 140:
            filas, anio, suelta = [], None, ""
            tablas.append(filas)
            continue
        if filas is None:
            continue
        if re.match(r"(?i)total carrera|titulaci[óo]n final|t[íi]tulo intermedio|actividades curriculares", limpia):
            filas = None if re.match(r"(?i)total carrera|titulaci[óo]n final|t[íi]tulo intermedio", limpia) else filas
            suelta = ""
            continue
        nuevo = anio_de(limpia)
        if nuevo:
            anio, suelta = nuevo, ""
            continue
        if re.search(r"(?i)cuatrimestre|^total", limpia):
            suelta = ""
            continue
        fila = _FILA_UNAHUR_2025.match(linea)
        if fila:
            filas.append({"n": int(fila.group(1)), "partes": [p for p in (suelta, clean_text(fila.group(2) or "")) if p],
                          "propio": bool(fila.group(2)), "abajo": False, "anio": anio})
            suelta = ""
            continue
        datos = _DATOS_UNAHUR_2025.match(linea)
        if datos:
            suelta = "\x00" + clean_text(datos.group(1))
            continue
        resto = re.match(r"^\s*(\d{1,2})\s+(\S.*)$", linea)
        if resto and suelta.startswith("\x00") and not re.search(r"\d", resto.group(2)):
            filas.append({"n": int(resto.group(1)), "partes": [suelta[1:], clean_text(resto.group(2))],
                          "propio": True, "abajo": True, "anio": anio})
            suelta = ""
            continue
        if re.search(r"\d", limpia):
            suelta = ""
            continue
        previa = filas[-1] if filas else None
        # The line below a row: that row's when its own cell was empty, or
        # its name goes on ("... de la" / "obstetricia"), or it starts in
        # lower case.
        if (previa and not previa["abajo"] and not suelta
                and (not previa["propio"] or _SIGUE.search(previa["partes"][-1]) or limpia[:1].islower())):
            previa["partes"].append(limpia)
            previa["abajo"] = True
            continue
        suelta = limpia
    for tabla in reversed(tablas):
        numeros = [f["n"] for f in tabla]
        if (tabla and numeros == list(range(1, len(numeros) + 1)) and all(f["anio"] for f in tabla)
                and all(f["partes"] for f in tabla)):
            materias: list[tuple[str, int]] = []
            for f in tabla:
                _agregar(materias, " ".join(f["partes"]), f["anio"])
            return desde_el_primero(materias)
    return []

def plan_unahur_todos(texto_con_columnas: str) -> list[tuple[str, int]]:
    """UNAHUR: its 2025 resolutions' layout first (the stricter reading),
    then the older brochures', then the 2025-2026 plan documents' table."""
    return (plan_unahur_2025(texto_con_columnas) or plan_unahur(texto_con_columnas)
            or plan_unahur_tabla(texto_con_columnas) or plan_unahur_campos(texto_con_columnas)
            or plan_unahur_numerado(texto_con_columnas))


_CUATRIMESTRE_UNAHUR = re.compile(r"(?i)^\s*(\d{1,2})\s*(?:er|do|ro|to|vo|mo|no|°|º)?\.?\s*cuatrimestre\s*$")
_ANIO_UNAHUR_NUMERADO = re.compile(r"(?i)^\s*(\d)\s*[°º]\s*año\s*$")
# "7   Análisis matemático I   cuatrimestral   6   96 ...", "3  Anatomo-Fisiología I  C  4  64",
# or the number alone when the name wraps around the row ("3   cuatrimestral  2  32",
# "29   20 (6)   100 ..."); or the field first ("1   Introducción al   CFE   4   64").
_FILA_UNAHUR_NUMERADA = re.compile(r"(?i)^\s*(\d{1,2})\s+(?:(\S.*?)\s{2,})?(?:cuatrimestral\b|anual\b|C\s|(?-i:C[A-Z]{2})\s|\d)")
# (Also the credits the plan counts apart: "40 créditos externos (160 horas)".)
_FIN_UNAHUR_NUMERADO = re.compile(r"(?i)^\s*(?:cr[ée]ditos|carga horaria total|total\b|\d+ cr[ée]ditos\b)")
# Between the rows: a cycle's heading, or the intermediate title and its
# hours ("Enfermero/a Universitario/a   1977   1356 ...").
_ENTRE_FILAS_UNAHUR = re.compile(r"(?i)^\s*(?:(?:primer|segundo|tercer)\s+ciclo\s*$|\S+/a\b)")


def plan_unahur_numerado(texto_con_columnas: str) -> list[tuple[str, int]]:
    """UNAHUR's tables numbered row by row (the tecnicaturas' brochures,
    Energía Eléctrica and Metalurgia; Enfermería's RCS 385/2024): under term
    headings ("1er. cuatrimestre", two to a year) or year headings ("1°
    Año"). A name too long for its cell is centred on its row, as many lines
    above as below it ("Nuevos Entornos y Lenguajes: la" / "3
    cuatrimestral 2 32" / "producción del conocimiento ..."; "Deontología y
    aspectos legales" / "27 del ejercicio profesional de la C 2 32" /
    "Enfermería"); of a wrapped line, the first column is the name's
    ("Práctica pre- Profesional   Mensual"). A line no row takes, one
    starting in lower case above a row, or a number out of order gives
    nothing; the plan ends at its "Créditos", "Carga horaria total" or
    "TOTAL" (or "40 créditos externos"). Credit slots ("Créditos ACA") are
    not subjects. A Roman figure typed as lower-case Ls ("Metalurgia ll")
    is the figure. A name may instead start on its row and go on below it,
    in lower case and with no blank line between (Viverismo: "1
    Introducción al  CFE  4  64" / "viverismo"). The page's motto
    ("“75 avo aniversario de la gratuidad ...”") is not part of the table."""
    filas: list[dict[str, Any]] = []
    anio = None
    arriba: list[str] = []
    abierta = None
    for linea in (texto_con_columnas or "").splitlines():
        # (A blank line ends a row's cell; a page's number or motto does not.)
        if not linea.strip():
            abierta = None
            continue
        if re.fullmatch(r"\s*\d{1,3}\s*", linea) or re.fullmatch(r"\s*“[^”]*”\s*", linea):
            continue
        termino, anual = _CUATRIMESTRE_UNAHUR.match(linea), _ANIO_UNAHUR_NUMERADO.match(linea)
        if termino or anual:
            if arriba:
                return []
            anio = (int(termino.group(1)) + 1) // 2 if termino else int(anual.group(1))
            abierta = None
            continue
        if anio is None:
            continue
        if _FIN_UNAHUR_NUMERADO.match(linea):
            break
        if _ENTRE_FILAS_UNAHUR.match(linea) and not _FILA_UNAHUR_NUMERADA.match(linea):
            if arriba:
                return []
            abierta = None
            continue
        fila = _FILA_UNAHUR_NUMERADA.match(linea)
        if fila:
            if arriba and arriba[0][:1].islower():
                return []
            nombre = clean_text(fila.group(2) or "")
            # (Of a row whose cell is empty, what was read is its length or hours.)
            if re.fullmatch(r"(?i)c|anual|mensual|cuatrimestral|\d.*", nombre):
                nombre = ""
            filas.append({"n": int(fila.group(1)), "anio": anio, "debajo": len(arriba),
                          "partes": arriba + ([nombre] if nombre else []), "sigue": not arriba and bool(nombre)})
            abierta = filas[-1] if arriba or nombre else None
            arriba = []
            continue
        parte = clean_text(re.split(r"\s{2,}", linea.strip())[0])
        if abierta is not None and abierta["debajo"]:
            abierta["partes"].append(parte)
            abierta["debajo"] -= 1
        elif abierta is not None and abierta["sigue"] and parte[:1].islower():
            abierta["partes"].append(parte)
        else:
            arriba.append(parte)
    numeros = [f["n"] for f in filas]
    if arriba or not filas or numeros != list(range(1, len(numeros) + 1)) or not all(f["partes"] for f in filas):
        return []
    materias: list[tuple[str, int]] = []
    for f in filas:
        nombre = re.sub(r"\s(l{1,3})$", lambda m: " " + "I" * len(m.group(1)), " ".join(f["partes"]))
        if not re.match(r"(?i)cr[ée]ditos\b", nombre):
            _agregar(materias, nombre, f["anio"])
    return desde_el_primero(materias)


_ANIO_UNAHUR_CAMPOS = re.compile(r"^\s*(PRIMER|SEGUNDO|TERCER|CUARTO|QUINTO|SEXTO)\s+A[ÑN]O\b(?:\s*\(.*\))?\s*$")
# "Zoología   C   CFE   6   96 ..." (the profesorados of 2024) or
# "Física   CFB   Cuatr.   64 ..." (Mantenimiento Hospitalario): the name,
# its length and its field, either way round, then the hours.
# (The length may read "C." or "C1": Geografía's and Chino's.)
_FILA_UNAHUR_CAMPOS = re.compile(r"^\s*(?:(\S.*?)\s{2,})?(?:[CA][.\d]?\s+C[A-Z]{1,3}|C[A-Z]{1,3}\s+(?:Cuatr\.|Anual|[CA]))\s+\d")


def plan_unahur_campos(texto_con_columnas: str) -> list[tuple[str, int]]:
    """UNAHUR's plans whose table has no subject numbers ("UNIDAD
    CURRICULAR  D  CP  HIS ...", the profesorados' resolutions of 2024):
    "PRIMER AÑO" alone over rows "Zoología  C  CFE  6  96 ...". A name too
    long for its cell is centred on its row, as many lines above as below
    ("Aprendizajes y prácticas" / "C CFB 4 64 ..." / "educativas"; with three,
    the middle one beside the data). A year's total, the intermediate
    title's line and a page's number are not subjects; the plan ends at
    "TOTAL CARRERA" or where the first year starts again."""
    materias: list[tuple[str, int]] = []
    anio = None
    arriba: list[str] = []
    abajo: list[str] = []
    debe_abajo = 0
    vistos: set[int] = set()
    for linea in texto_con_columnas.splitlines():
        texto = clean_text(linea).replace("\xa0", " ").strip()
        cabeza = _ANIO_UNAHUR_CAMPOS.match(linea)
        if cabeza:
            nuevo = _ORDINALES[cabeza.group(1).lower()]
            if nuevo in vistos:
                break
            vistos.add(nuevo)
            anio, arriba, debe_abajo = nuevo, [], 0
            continue
        if anio is None or not texto:
            continue
        if re.match(r"(?i)total (?:de la )?carrera|titulaci[óo]n final", texto.translate(_LIGADURAS)):
            break
        fila = _FILA_UNAHUR_CAMPOS.match(linea)
        if fila:
            nombre = [*arriba, *([clean_text(fila.group(1))] if fila.group(1) else [])]
            if not nombre:
                return []
            abajo = nombre
            materias.append((" ".join(nombre), anio))
            # (A name on its row that stops on a connector goes on below,
            # past a page break: "Historia de la Nación Argentina y sus" /
            # "13" / "proyectos educativos".)
            debe_abajo, arriba = len(arriba) or int(bool(_SIGUE.search(nombre[-1]) or nombre[-1].endswith(" sus"))), []
            continue
        # A row split over lines ("C" here, its field and hours on the next):
        # a row this does not read, so not the whole plan.
        if re.search(r"(?:^|\s{2,})(?:[CA][.\d]?|C[A-Z]{1,3})(?:\s{2,}|$)", linea.strip()):
            return []
        # A page's number: the name may go on after it.
        if re.fullmatch(r"\d{1,3}", texto):
            continue
        # A name beside hours that are not a row's ("Activos   64   61"):
        # the rest of a row split over lines.
        if (re.match(r"[^\W\d_][^\d]*?\s{2,}\d", linea.strip())
                and not re.match(r"(?i)total|actividades|cr[ée]ditos|t[íi]tulaci|t[ée]cnic", texto)):
            return []
        # A total, the intermediate title's hours.
        if re.search(r"\d", texto) or re.match(r"(?i)total|actividades curriculares", texto):
            arriba, debe_abajo = [], 0
            continue
        if debe_abajo:
            abajo.append(texto)
            materias[-1] = (" ".join(abajo), anio)
            debe_abajo -= 1
        else:
            arriba.append(texto)
    resultado: list[tuple[str, int]] = []
    for nombre, anio in materias:
        _agregar(resultado, nombre, anio)
    return desde_el_primero(resultado)


def plan_ffyb_uba(texto: str) -> list[tuple[str, int]]:
    """UBA, Farmacia y Bioquímica: the plan's resolution as ``pdftotext
    -layout`` gives it, its subjects under "3° Cuatrimestre" headings (two
    terms a year), each numbered and with its CBC code ("01. Matemática
    (51)"), the name wrapped on the lines below (across a page break too)
    until the next number or the term's note. The other columns (character,
    duration, hours, prerequisites) start where "Obligatoria" or a wide gap
    does. The elective slots ("38. Asignatura Optativa 1") name no subject;
    the plan ends at the resolution's next numbered section ("13) Carga
    horaria...")."""
    materias: list[tuple[str, int]] = []
    anio: int | None = None
    actual: list[str] = []
    columna = re.compile(r"\s{2,}|\s+(?:Obligatoria|Optativa|Electiva|optativa|obligatoria)\b")

    def cerrar() -> None:
        if actual and anio:
            nombre = re.sub(r"\s*\(\d{1,3}\)\s*$", "", " ".join(actual))
            if not re.match(r"(?i)^asignatura\b", nombre):
                _agregar(materias, nombre, anio)
        actual.clear()

    for linea in (texto or "").splitlines():
        cuatrimestre = re.match(r"^\s*(\d{1,2})\s*[°º]\s*Cuatrimestre\b", linea)
        if cuatrimestre:
            cerrar()
            anio = (int(cuatrimestre.group(1)) + 1) // 2
            continue
        if anio and re.match(r"^\s*\d{1,2}\)\s", linea):
            break
        numero = re.match(r"^\s{0,3}\d{2}\.\s*(\S.*)$", linea)
        if numero and anio:
            cerrar()
            actual.append(columna.split(numero.group(1).strip())[0])
        elif re.match(r"(?i)^\s*(\(duraci[óo]n|estas asignaturas|asignaturas con|\(\d+\s*hs?\))", linea):
            cerrar()
        elif actual and re.match(r"^\s{0,6}\S", linea):
            izquierda = columna.split(linea.strip())[0]
            if not re.match(r"(?i)^(cbc|tp|final|aprobad|p[áa]gina)", izquierda):
                actual.append(izquierda)
    cerrar()
    return desde_el_primero(materias)


plan_ffyb_uba.respaldo = True


_SEMESTRES = {"primer": 1, "primero": 1, "segundo": 2, "tercer": 3, "tercero": 3, "cuarto": 4,
              "quinto": 5, "sexto": 6, "séptimo": 7, "septimo": 7, "octavo": 8, "noveno": 9,
              "décimo": 10, "decimo": 10, "undécimo": 11, "undecimo": 11, "duodécimo": 12, "duodecimo": 12}


def plan_por_semestres(html: str) -> list[tuple[str, int]]:
    """UNC Ciencias Económicas: the plan on the career's page, a heading per
    term ("Primer semestre", "Décimo semestre", "3° semestre") and its
    subjects in bullets below it; two terms a year. The levelling cycle
    before the first term is not the plan."""
    soup = BeautifulSoup(html or "", "html.parser")
    for sobra in soup(["script", "style", "nav", "header", "footer"]):
        sobra.decompose()
    materias: list[tuple[str, int]] = []
    anio: int | None = None
    for linea in soup.get_text("\n").split("\n"):
        linea = clean_text(linea).replace("\xa0", " ").strip()
        if not linea:
            continue
        semestre = re.fullmatch(r"(?i)(\w+|\d{1,2}\s*[°º])\s+(?:semestre|cuatrimestre)", linea)
        if semestre:
            clave = semestre.group(1).lower().rstrip("°º ").strip()
            numero = int(clave) if clave.isdigit() else _SEMESTRES.get(clave)
            anio = (numero + 1) // 2 if numero else None
            continue
        if re.match(r"(?i)^(?:::|ciclo\b|>|consultar)", linea):
            continue
        viñeta = re.match(r"^[•·▪]\s*(.+)$", linea)
        if anio and viñeta:
            _agregar(materias, viñeta.group(1).rstrip("."), anio)
        elif materias and re.match(r"(?i)^(diálogo|dialogo|requisitos|título|titulo)", linea):
            break
    return desde_el_primero(materias)


def plan_famaf(html: str) -> list[tuple[str, int]]:
    """UNC, FAMAF: the career's plan as cards, a ``div.year`` per year (its
    label "1º año") and a ``div.subject`` per subject, its name the card's
    first link. The levelling course is not in a year."""
    materias: list[tuple[str, int]] = []
    for bloque in BeautifulSoup(html or "", "html.parser").select("div.year"):
        anio = anio_de(_texto(bloque.select_one(".label")))
        for materia in bloque.select("div.subject"):
            enlace = materia.find("a")
            if anio and enlace:
                # "Análisis Matemático I (LC - LMA - LHM)": the careers that share it.
                _agregar(materias, re.sub(r"\s*\([A-Z]{2,4}(?:\s*-\s*[A-Z]{2,4})*\)\s*$", "", _texto(enlace)), anio)
    return desde_el_primero(materias)


def plan_tabla_por_encabezados(html: str) -> list[tuple[str, int]]:
    """A plan's table whose header names its columns: the subject's
    ("Nombre", "Asignatura", "Cursos", "Materia") and the year's ("Año"), or
    the year in a row of its own above ("PRIMER AÑO"). UNLP Informática (a
    code, the name, how long, prerequisites) and Económicas (the cycle in a
    cell spanning its rows, then course, term, year, hours): rows are aligned
    from the right, where a spanning cell does not shift them. A course of
    weeks before the first term (Informática's "6 Semanas") is the levelling
    course, not the plan; a row announcing the electives ends it."""
    materias: list[tuple[str, int]] = []
    for tabla in BeautifulSoup(html or "", "html.parser").find_all("table"):
        cabecera: list[str] | None = None
        anio_de_la_fila: int | None = None
        for fila in tabla.find_all("tr"):
            celdas = [_texto(c) for c in fila.find_all(["td", "th"])]
            if len(celdas) == 1 or (celdas and all(not c for c in celdas[1:])):
                # "ELEGIR DOS OPTATIVAS SEGÚN LA ORIENTACIÓN": the pool of
                # electives that follows is not the plan.
                if re.search(r"(?i)optativ|orientaci[óo]n|electiv", celdas[0]):
                    break
                anio_de_la_fila = anio_de(celdas[0]) or anio_de_la_fila
                continue
            claves = [comparison_key(c) for c in celdas]
            if any(c in ("nombre", "asignatura", "asignaturas", "cursos", "materia", "materias") for c in claves):
                cabecera = claves
                continue
            if not cabecera:
                continue
            nombre_i = next(i for i, c in enumerate(cabecera)
                            if c in ("nombre", "asignatura", "asignaturas", "cursos", "materia", "materias"))
            desde_la_derecha = len(cabecera) - nombre_i
            if len(celdas) < desde_la_derecha:
                continue
            nombre = celdas[-desde_la_derecha]
            anio = anio_de_la_fila
            if "ano" in cabecera:
                atras = len(cabecera) - cabecera.index("ano")
                numero = re.match(r"\s*(\d)", celdas[-atras]) if len(celdas) >= atras else None
                anio = int(numero.group(1)) if numero else None
            if any(re.search(r"(?i)\d+\s*semanas", c) for c in celdas) or not re.search(r"[A-Za-zÁÉÍÓÚáéíóú]{3}", nombre):
                continue
            _agregar(materias, nombre, anio)
    return desde_el_primero(materias)


def plan_bloques_numerados(texto: str) -> list[tuple[str, int]]:
    """UNNE Derecho: the plan PDF as ``pdftotext -layout`` gives it, each
    year a block of numbered subjects ("8. Derecho de las obligaciones")
    with the year written beside the middle of the block ("Segundo año
    Obligatorias") and two blank lines between blocks. An orientation's
    elective ("36-A. Defensa del Estado en juicio") is not the plan."""
    materias: list[tuple[str, int]] = []
    texto = (texto or "").replace("\ufb01", "fi").replace("\ufb02", "fl")
    # Blocks part at two blank lines, and at the table's header repeated on a new page.
    for bloque in re.split(r"\n\s*\n\s*\n|\n\s*A[ñn]o\s+Car[áa]cter[^\n]*", texto):
        rotulo = re.search(r"(?im)^\s*(primer|segundo|tercer|cuarto|quinto|sexto)\s+a[ñn]o\b", bloque)
        if not rotulo:
            continue
        anio = _ORDINALES[rotulo.group(1).lower()]
        for numerada in re.finditer(r"(?m)(?:^|\s{2,})\d{1,2}\.\s+(\S.*?)(?=\s{2,}|$)", bloque):
            _agregar(materias, numerada.group(1), anio)
    return desde_el_primero(materias)


plan_bloques_numerados.respaldo = True


def plan_odn_unne(html: str) -> list[tuple[str, int]]:
    """UNNE Odontología: the plan on its page year by year, each "unidad
    curricular" marked "UC." (or a "Seminario") and followed by a row of how
    it runs ("Cuatrimestral Presencial 6 hs 96 hs"); a name that does not
    fit wraps to a row of its own ("UC. Odontología Integral–Práctica" /
    "Profesional Supervisada")."""
    materias: list[tuple[str, int]] = []
    for nombre, anio in plan_texto_por_anio(html):
        if re.match(r"(?i)^(cuatrimestral|semestral|anual|bimestral)\b", nombre):
            continue
        if re.match(r"(?i)^(uc\.|seminario)\s*", nombre) or not materias:
            materias.append((re.sub(r"(?i)^uc\.\s*", "", nombre), anio))
        else:
            materias[-1] = (materias[-1][0] + " " + nombre, materias[-1][1])
    return desde_el_primero(materias)


def plan_unicen_sin_anios(html: str) -> list[tuple[str, int | None]]:
    """UNICEN's central career pages that list the plan without years (its
    Licenciatura en Historia): the list under "Plan de estudios", only when
    nothing in it says a year or a term. Read without years, so the plan
    counts only with twenty subjects or more (``MINIMO_SIN_ANIO``)."""
    soup = BeautifulSoup(html or "", "html.parser")
    seccion = next((s for s in soup.select("div.seccion-carrera")
                    if "plan de estudio" in _texto(s.select_one("h3.titulo")).lower()), None)
    cuerpo = seccion.select_one("div.cuerpo") if seccion else None
    if not cuerpo or re.search(r"(?i)\b(a[ñn]o|cuatrimestre|semestre)\b", _texto(cuerpo)):
        return []
    materias: list[tuple[str, int]] = []
    for item in cuerpo.find_all("li"):
        _agregar(materias, _texto(item), 1)
    return [(nombre, None) for nombre, _ in materias]


def plan_uch(texto: str) -> list[tuple[str, int]]:
    """The Universidad del Chubut's plan sheets (``-layout`` text): a row per
    subject, its number first ("1    Derecho Privado Parte General   -
    Cuatrimestral   Promocional"), under the term it is in ("Primer
    Semestre" / "Segundo Cuatrimestre"). The year's label ("1° AÑO") sits in
    the margin halfway down its rows, so the year is counted by the terms
    instead: each "Primer" term opens the next. A name the cell wrapped goes
    on in the next line ("Derecho Internacional Público y de la" /
    "Integración"); an elective ("Optativa I:") is a choice, and it and the
    options listed under it are left out, as are the "Otros requisitos".

    A sheet whose numbers start over (Corredor y Martillero's third year, one
    per title) is two plans, and a sheet whose font the text does not
    decode ("so\ufffdtware", Sistemas' "SŰŁĨŰō...") cannot be read: neither is taken."""
    materias: list[list] = []
    anio, ultima, numeros, columna = 0, None, set(), 0
    for linea in texto.splitlines():
        cuerpo = re.sub(r"^\s*\d\s*[°º]\s*AÑO\b", "", linea).strip()
        sangria = len(linea) - len(linea.lstrip())
        if re.fullmatch(r"(?i)primer\s+(?:semestre|cuatrimestre)", cuerpo):
            anio, ultima = anio + 1, None
            continue
        if re.fullmatch(r"(?i)segundo\s+(?:semestre|cuatrimestre)|otros requisitos", cuerpo):
            ultima = None
            continue
        fila = re.match(r"(\d{1,2})\s+(.+?)(?:\s{2,}|$)", cuerpo)
        if fila and anio and re.search(r"(?i)cuatrimestral|anual|semestral", cuerpo):
            # (The "ﬁ" ligature of Diseño's sheets is two letters.)
            nombre = clean_text(unicodedata.normalize("NFKC", fila.group(2)))
            if fila.group(1) in numeros:
                return []
            numeros.add(fila.group(1))
            if re.match(r"(?i)optativa|electiva", nombre):
                ultima = None
                continue
            ultima = [nombre, anio]
            materias.append(ultima)
            columna = linea.index(fila.group(2), linea.index(fila.group(1)) + len(fila.group(1)))
        # (A name's next piece starts under it, not under the correlatives: "Todos los espacios" / "curriculares".)
        elif ultima and cuerpo and abs(sangria - columna) <= 3 and not re.search(r"\s{3,}", cuerpo) and (re.search(
                r"(?i)\b(?:de|del|la|las|los|y|e|en|a|con|para)$", ultima[0]) or cuerpo[0].islower()):
            ultima[0] = clean_text(f"{ultima[0]} {cuerpo}")
            ultima = None
    if any(re.search(r"[^\w\s.,;:()/'\"-]|[^\x00-\xff]", nombre) for nombre, _ in materias):
        return []
    return [(nombre, anio) for nombre, anio in materias]


def plan_unab(cajas: str) -> list[tuple[str, int]]:
    """UNAB's plan sheets (``-bbox-layout``): two years to a column, a row
    per subject (its code, its name, its correlatives and hours), each term
    closed by "TOTAL CUATRIMESTRE" and each year by "TOTAL ANUAL". The
    year's label ("PRIMER AÑO") sits in the margin halfway down its rows and
    the codes do not always share the name's line, so a name is any line
    that starts at the column's names (around the left edge of "TOTAL
    ANUAL") and its year is the count of "TOTAL ANUAL" above it, column
    after column, page after page. A name the cell wrapped is two lines
    closer together than two rows are ("Herramientas computacionales y
    programación" / "04. para la ingeniería y la ciencia", its number on
    the second); the number ("04.") and the term an annual subject is
    listed under ("(1° cuatr. asignatura anual)") are not part of it, and a
    subject listed under both terms is one."""
    renglones = _renglones(cajas)
    cierres = [(p, x, y) for p, x, y, t in renglones if t == "TOTAL ANUAL"]
    if not cierres:
        return []
    columnas = sorted({(p, round(x)) for p, x, _ in cierres})
    materias: list[tuple[str, int]] = []
    anio = 0
    for pagina, borde in columnas:
        propios = sorted(y for p, x, y in cierres if p == pagina and abs(x - borde) <= 4)
        lineas = sorted((y, t) for p, x, y, t in renglones if p == pagina and -4 <= x - borde <= 20
                        and not re.match(r"TOTAL|CARGA HORARIA", t) and re.search(r"[A-Za-zÁÉÍÓÚáéíóúñÑ]", t))
        grupos: list[list] = []
        for y, texto in lineas:
            if grupos and y - grupos[-1][-1][0] < 10:
                grupos[-1].append((y, texto))
            else:
                grupos.append([(y, texto)])
        for grupo in grupos:
            nombre = clean_text(" ".join(re.sub(r"^\d{1,2}\.\s*", "", t) for _, t in grupo))
            # ("micro-" / "procesadores")
            nombre = re.sub(r"(\w)- (?=[a-záéíóú])", r"\1", nombre)
            nombre = clean_text(re.sub(r"\s*\([^)]*\b(?:anual|cuatr)[^)]*\)", "", nombre, flags=re.I))
            nuevo = (nombre, anio + 1 + sum(1 for cierre in propios if cierre < grupo[0][0]))
            if nombre and nuevo not in materias:
                materias.append(nuevo)
        # A column that ends in a year's middle (a fifth year's single term) goes on in the next.
        anio += len(propios)
    return materias
plan_unab.cajas = True  # type: ignore[attr-defined]


def plan_undelta(texto: str) -> list[tuple[str, None]]:
    """UNDelta's plan documents (``-layout`` text): no subject's year, only
    each field of the training and its subjects ("El CFD comprende las
    siguientes asignaturas:" and a name per line). A field's list ends at
    the next field ("Campo de Formación ..."), at the "Estructura
    curricular" or at prose (a long line, or one closing a sentence). The
    electives ("Electiva I") are a choice, not a subject; the lists' bullets,
    their page's section numbers ("2.1") and the cycle's heading ("1° Ciclo")
    are not part of a name.

    The lists split a long name over two of their lines just as they
    separate two names ("Tendencias Globales en el Uso del Agua, Innovación
    y Nuevos" / "Negocios del Agua"), so each name is checked against the
    rest of the document, where the minimum contents head each subject:
    two of the list's lines whose join is found there are one name, and a
    document with a name not found there (a word the text broke, "Polític
    a") is not read."""
    lineas = texto.splitlines()
    listas: list[list[str]] = []
    en_lista: set[int] = set()
    lista = None
    for numero, linea in enumerate(lineas):
        cuerpo = clean_text(linea)
        if re.search(r"(?i)comprende las siguientes asignaturas:?$", cuerpo):
            lista = []
            listas.append(lista)
            continue
        if lista is None or not cuerpo:
            continue
        if (re.match(r"(?i)campo de formaci|estructura curricular|contenidos m[ií]nimos|>>", cuerpo)
                or len(cuerpo) > 75 or cuerpo.endswith((".", ":")) or re.match(r"[a-z]", cuerpo)):
            lista = None
            continue
        en_lista.add(numero)
        cuerpo = clean_text(re.sub(r"^(?:[•·]|\d\.\d)\s*", "", cuerpo))
        if not cuerpo or re.fullmatch(r"[\d.\s]+|\d\s*[°º]\s*ciclo|[^a-záéíóúñ]+", cuerpo, re.I) or cuerpo.isupper():
            continue
        # ("Inglés Il", "Práctica Profesional Il": the numeral typed with an "l".)
        lista.append(re.sub(r"\b(?:Il|ll)$", "II", cuerpo))
    resto = " " + re.sub(r"\s+", " ", " ".join(l for n, l in enumerate(lineas) if n not in en_lista)).lower() + " "

    def esta(nombre: str) -> bool:
        return re.search(r"(?<!\w)" + re.escape(nombre.lower()) + r"(?!\w)", resto) is not None

    materias: list[tuple[str, None]] = []
    for nombres in listas:
        indice = 0
        while indice < len(nombres):
            nombre = nombres[indice]
            if indice + 1 < len(nombres) and esta(f"{nombre} {nombres[indice + 1]}"):
                nombre = f"{nombre} {nombres[indice + 1]}"
                indice += 1
            indice += 1
            if re.match(r"(?i)electiva|optativa", nombre):
                continue
            # A short name the contents call otherwise ("Cultura General de la
            # Universidad", "... en la Universidad" there) is the list's; a long
            # one may be the first line of a name, and then the document is not read.
            if not esta(nombre) and len(nombre) > 50:
                return []
            # A word the text broke ("Polític a", "Derech o"): the document is not read.
            if re.search(r"\w\s[a-záéíóú]$", nombre):
                return []
            if (nombre, None) not in materias:
                materias.append((nombre, None))
    return materias


def plan_unl(html: str) -> list[tuple[str, int]]:
    """The UNL's distance careers: under "plan de estudios" each year's
    heading ("PRIMER AÑO") and its subjects, each marked "•" and wrapped
    over lines of its own ("•Introducción a la Bibliotecología y Ciencia" /
    "de la Información"). The plan ends where its lines stop being a year
    or a subject ("+ Información en UNLVirtual")."""
    soup = BeautifulSoup(html or "", "html.parser")
    titulo = next((p for p in soup.select("p.meta-carreras") if clean_text(p.get_text()).lower() == "plan de estudios"), None)
    if titulo is None:
        return []
    lineas = []
    for hermano in titulo.find_next_siblings():
        lineas += [clean_text(t) for t in hermano.get_text("\n").split("\n")]
    materias: list[list] = []
    anio, ultima = None, None
    for linea in lineas:
        if not linea:
            continue
        encontrado = anio_de(linea)
        if encontrado and re.fullmatch(r"(?i)\S+\s+a[ñn]o:?|\d\s*[°º]?\s*a[ñn]o:?", linea):
            anio, ultima = encontrado, None
        elif linea.startswith(("•", "·")) and anio:
            ultima = [clean_text(linea.lstrip("•· ")), anio]
            materias.append(ultima)
        # A line of its own that is neither is the last name's next piece
        # ("Servicios de Información y Referencia" / "Especializada").
        # A note on the career ("*Carrera compartida entre FCA, FCV y FCE.") ends the plan.
        elif (ultima and len(linea) < 60 and not linea.endswith(".")
              and not re.match(r"(?i)[+©*]|pod[ée]s|m[áa]s informaci", linea)):
            ultima[0] = clean_text(f"{ultima[0]} {linea}")
        elif materias:
            break
    vistas: list[tuple[str, int]] = []
    for nombre, anio in materias:
        # An elective ("Optativa I") is a choice, not a subject.
        if (nombre, anio) not in vistas and not re.match(r"(?i)optativa|electiva", nombre):
            vistas.append((nombre, anio))
    return vistas


def plan_ub(cajas: str) -> list[tuple[str, int]]:
    """The UB's career brochures (``-bbox-layout``): a column per two years,
    each year's heading ("PRIMER AÑO") over its terms and their subjects,
    each marked "•"; a name the column wrapped goes on indented under its
    text ("• Derechos de la Propiedad Industrial e" / "Intelectuales"). A
    subject is a mark under a year's heading in its column: the brochure's
    other lists (agreements abroad, the electives offered) have none. The
    elective slots ("Materia Optativa de Formación General (MOFG) 1",
    "MOFE 2") are a choice, not a subject."""
    renglones = sorted(_renglones(cajas), key=lambda r: (r[0], r[2]))
    # A year by orientation ("CUARTO AÑO ORIENTACIÓN PERIODISMO"): two plans, neither read.
    if any(re.match(r"(?:PRIMER|SEGUNDO|TERCER|CUARTO|QUINTO|SEXTO)\s+AÑO\s+ORIENTACI", t) for _, _, _, t in renglones):
        return []
    titulos = [(p, x, y, anio_de(t)) for p, x, y, t in renglones
               if re.fullmatch(r"(?:PRIMER|SEGUNDO|TERCER|CUARTO|QUINTO|SEXTO)\s+AÑO", t)]
    materias: list[list] = []
    ultima: dict[float, list] = {}
    for pagina, x, y, texto in renglones:
        arriba = [(ty, anio) for p, tx, ty, anio in titulos if p == pagina and ty < y and -12 <= x - tx <= 12]
        if not arriba:
            continue
        anio = max(arriba)[1]
        columna = round(x / 40)
        if texto.startswith("•"):
            ultima[columna] = [clean_text(texto.lstrip("• ")), anio, x, y]
            materias.append(ultima[columna])
        elif (columna in ultima and 2 <= x - ultima[columna][2] <= 10 and y - ultima[columna][3] < 12
              and not re.search(r"(?i)semestre|cuatrimestre", texto)):
            ultima[columna][0] = clean_text(f"{ultima[columna][0]} {texto}")
            ultima[columna][3] = y
        else:
            ultima.pop(columna, None)
    return sorted(((nombre, anio) for nombre, anio, _, _ in materias
                   if not re.search(r"(?i)optativa|\bMOF[EG]\b", nombre)), key=lambda m: m[1])


plan_ub.cajas = True  # type: ignore[attr-defined]


def plan_ub_distancia(cajas: str) -> list[tuple[str, int]]:
    """The UB's distance careers (``-bbox-layout``): under "Síntesis de los
    Contenidos" a table of year, term and subject, the subjects numbered
    ("1. Principios de Administración") and each label ("1º") somewhere
    along its cell's rows. A cell's rows are closer together than two
    cells are; a cell's term is the label in the term's column that sits
    beside it, and the year is counted by the cells, a first term opening
    the next. The list ends at the "Obligaciones Académicas"."""
    renglones = sorted(_renglones(cajas), key=lambda r: (r[0], r[2]))
    inicio = next(((p, y) for p, x, y, t in renglones if re.fullmatch(r"(?i)s[íi]ntesis de los contenidos", t)), None)
    cabeza = {t.upper(): x for p, x, y, t in renglones if t.upper() in ("AÑO", "CUATRIMESTRE")}
    if inicio is None or len(cabeza) < 2:
        return []
    fin = next(((p, y) for p, x, y, t in renglones if (p, y) > inicio
                and re.fullmatch(r"(?i)obligaciones acad[ée]micas", t)), None)
    medio = (cabeza["AÑO"] + cabeza["CUATRIMESTRE"]) / 2
    filas, etiquetas = [], []
    for p, x, y, t in renglones:
        if (p, y) <= inicio or (fin and (p, y) >= fin):
            continue
        fila = re.fullmatch(r"(\d{1,2})\.\s+(\S.*)", t)
        if fila:
            filas.append((p, y, int(fila.group(1)), clean_text(fila.group(2))))
        elif re.fullmatch(r"[12]\s*[º°]", t) and x > medio and x < cabeza["CUATRIMESTRE"] + 80:
            etiquetas.append((p, y, int(t[0])))
    if not filas or [n for _, _, n, _ in filas] != list(range(1, len(filas) + 1)):
        return []
    pasos = sorted(b[1] - a[1] for a, b in zip(filas, filas[1:]) if a[0] == b[0] and b[1] > a[1])
    paso = pasos[len(pasos) // 4] if pasos else 12
    bloques: list[list] = []
    for fila in filas:
        if bloques and fila[0] == bloques[-1][-1][0] and fila[1] - bloques[-1][-1][1] < 1.6 * paso:
            bloques[-1].append(fila)
        else:
            bloques.append([fila])
    materias, anio = [], 0
    for bloque in bloques:
        pagina, arriba, abajo = bloque[0][0], bloque[0][1], bloque[-1][1]
        suyas = [e for p, y, e in etiquetas if p == pagina and arriba - paso <= y <= abajo + paso]
        if len(suyas) != 1:
            return []
        if suyas[0] == 1 or not anio:
            anio += 1
        materias += [(nombre, anio) for _, _, _, nombre in bloque]
    return materias


plan_ub_distancia.cajas = True  # type: ignore[attr-defined]


def plan_ub_todos(cajas: str) -> list[tuple[str, int]]:
    """The UB's documents: a career brochure, or a distance career's table."""
    return plan_ub(cajas) or plan_ub_distancia(cajas)


plan_ub_todos.cajas = True  # type: ignore[attr-defined]


def plan_ub_documento(ruta: str) -> list[tuple[str, int | None]]:
    """The UB's documents, whichever their layout: a brochure or a distance
    career's table (``plan_ub_todos``, on the text's boxes), else a distance
    career's sheet with its subjects numbered (``plan_numerado_ub``)."""
    import subprocess

    def texto(modo: str) -> str:
        return subprocess.run(["pdftotext", modo, ruta, "-"], capture_output=True, text=True, timeout=60).stdout

    return plan_ub_todos(texto("-bbox-layout")) or plan_numerado_ub(texto("-layout"))


plan_ub_documento.ruta = True  # type: ignore[attr-defined]


def plan_uader_gestion(texto: str, carrera: str = "") -> list[tuple[str, int]]:
    """UADER's Ciencias de la Gestión documents (``-layout`` text): each
    year's table ("1º Año", "2do Año") with a row per subject, its six-digit
    code first (its fourth digit the year, 202101, where the table has no
    heading) and its dedication ("ANUAL", "A", "C1"). A name the cell
    wrapped sits above and below its code's line ("Principios de" /
    "202101  ANUAL ..." / "Administración"), or beside it. One document
    often holds the tecnicatura and the licenciatura it leads to ("Plan de
    Estudio Licenciatura en Marketing", or a "Tecnicatura y Licenciatura"
    document's fourth year on): a tecnicatura's career takes its part only.
    The electives ("Asignatura Optativa", "Idioma optativo", "Electiva") and
    the internship are a choice or a requirement, not a subject."""
    lineas = texto.splitlines()
    materias: list[tuple[str, int]] = []
    tecnicatura = comparison_key(carrera).startswith("tecnic")
    ambas = bool(re.match(r"(?i)\s*tecnicatura y licenciatura", next((l for l in lineas if l.strip()), "")))
    titulo = None
    for numero, linea in enumerate(lineas):
        if tecnicatura and re.match(r"(?i)\s*plan de estudios? licenciatura", linea):
            break
        encabezado = re.match(r"(?i)^\s*(\d)\s*(?:º|°|do|er|ro|to)\s*año\s*$", linea)
        if encabezado:
            titulo = int(encabezado.group(1))
            if tecnicatura and ambas and titulo > 3:
                break
            continue
        fila = re.match(r"^\s*(20\d)(\d)(\d{2})\s+(.*?)\s*(ANUAL|C1 ó C2|C[12]|A)(?=\s|$)", linea)
        if not fila:
            continue
        nombre = clean_text(fila.group(4))
        if not nombre:
            arriba = lineas[numero - 1] if numero else ""
            abajo = lineas[numero + 1] if numero + 1 < len(lineas) else ""
            piezas = [clean_text(re.split(r"\s{3,}", l.strip())[0]) for l in (arriba, abajo)
                      if l.strip() and not re.match(r"^\s*\d{6}\b", l) and not re.search(r"(?i)\baño\s*$", l)]
            nombre = clean_text(" ".join(piezas))
        if not nombre or re.search(r"(?i)optativ|electiva|pasant[ií]a", nombre):
            continue
        materias.append((nombre, titulo or int(fila.group(2))))
    return materias


plan_uader_gestion.carrera = True  # type: ignore[attr-defined]


_FIN_DEL_PLAN_USI = re.compile(r"(?i)^(?:otros requisitos|contenidos m[ií]nimos|materias (?:electivas|adicionales)|"
                               r"director|directora|texto del bot|habilidades|publicado|respaldo|t[íi]tulo|requisitos|"
                               r"perfil|alcances|inscrip|consult|modalidad|duraci[óo]n|cuerpo docente|proceso de admisi|"
                               r"ordenanza|resoluci[óo]n|extras$|instagram|facebook|twitter|linkedin|youtube|folleto|"
                               r"horario|©|copyright|comunidad$|si quer[ée]s|quiero recibir|correo|tel[ée]fono|"
                               r"facultad de|una formaci|direcci[óo]n de alumnos)")


def plan_anios_y_renglones(html: str) -> list[tuple[str, int]]:
    """A career's page that lays its plan out under each year's heading
    ("Primer Año"), maybe its terms ("PRIMER CUATRIMESTRE"), a subject per
    line (USI, UDEMM, UNLC). The plan ends at the page's next section ("Otros
    Requisitos", "Contenidos Mínimos", "Director de la Carrera", "Proceso
    de admisión"), at a line that is not a subject's (a sentence), or at a
    year that does not follow. The electives ("Electiva I", "Optativa II")
    are a choice; a subject's term after its name ("(2º cuatrimestre)") and
    the list's marks ("·") are not part of it."""
    soup = BeautifulSoup(html or "", "html.parser")
    for quitar in soup(["script", "style", "nav", "header", "footer", "noscript"]):
        quitar.decompose()
    lineas = [clean_text(t) for t in soup.get_text("\n").split("\n") if clean_text(t)]
    materias: list[tuple[str, int]] = []
    anio = None
    for linea in lineas:
        encontrado = anio_de(linea)
        if encontrado:
            if anio and encontrado <= anio:
                break
            anio = encontrado
            continue
        if anio is None:
            continue
        linea = clean_text(re.sub(r"^[·•.\-–]\s*", "", linea))
        if re.fullmatch(r"(?i)(primer|segundo)\s+(cuatrimestre|semestre)|anual(es)?|\d+|asignatura anual|modular|materias", linea):
            continue
        # (UMaza closes each degree's years with it: "Licenciado en Recursos Humanos (4 años)".)
        if (_FIN_DEL_PLAN_USI.match(linea) or len(linea) > 90 or linea.endswith((".", ":")) or "@" in linea
                or re.search(r"(?i)\(\d+(?:[.,]5)?\s*a[ñn]os\)$", linea)):
            break
        if re.match(r"(?i)(?:\d+\s*[.-]\s*)?(?:electiva|optativa)", linea):
            continue
        linea = re.sub(r"(?i)\s*\((?:\d\s*[º°]\s*cuatrimestre|anual|semestral)\)$", "", linea)
        _agregar(materias, linea, anio)
    # A page whose rows run into each other ("... Anual Portugués II
    # Semestral (1º)", UNSJ's Turismo) is not read.
    if any(re.search(r"\b(?:Semestral|Anual)\b(?:\s*\(\d\s*[º°]\))?(?:\s+\S|$)", n) for n, _ in materias):
        return []
    return materias



def plan_umendoza(texto: str) -> list[tuple[str, int]]:
    """Universidad de Mendoza's engineering plan sheets (``-layout`` text):
    each year's heading ("PRIMER AÑO") over a row per subject, maybe its
    term first ("1", "2", "Anual"), then its code ("0005", "1020") and its
    name. The leveling course ("CPREC  PRECALCULO") is the admission's, not
    the plan's. Names in capitals are written as names."""
    materias: list[tuple[str, int]] = []
    anio = None
    for linea in texto.splitlines():
        encabezado = re.match(r"^\s*(PRIMER|SEGUNDO|TERCER|CUARTO|QUINTO|SEXTO)\s+AÑO\b", linea)
        if encabezado:
            anio = _ORDINALES[encabezado.group(1).lower()]
            continue
        fila = re.match(r"^\s*(?:[1-2]|Anual)?\s+(\d{3,4})\s+(\S.*?)(?:\s{2,}|$)", linea)
        if fila and anio:
            _agregar(materias, fila.group(2), anio)
    return materias
plan_umendoza.respaldo = True  # type: ignore[attr-defined]  # its other layouts go to the general reader


def plan_fce_unse(html: str) -> list[tuple[str, int]]:
    """UNSE Ciencias Exactas' plan pages ("ic-planinnov2026"): a block per
    year (``.fceyt-pe-year``, its label "Primer año") holding its modules'
    tables, a row per subject (its number, its name, its correlatives).
    The electives, outside the years' blocks, are left out, as are the rows
    that do not start with a number."""
    materias: list[tuple[str, int]] = []
    for bloque in BeautifulSoup(html or "", "html.parser").select(".fceyt-pe-year"):
        rotulo = bloque.select_one(".fceyt-pe-year-toggle")
        anio = anio_de(_texto(rotulo)) if rotulo else None
        if not anio:
            continue
        for fila in bloque.select("tr"):
            celdas = [_texto(c) for c in fila.find_all(["td", "th"])]
            if len(celdas) >= 2 and re.fullmatch(r"\d{1,2}", celdas[0]) and celdas[1]:
                _agregar(materias, celdas[1], anio)
    return desde_el_primero(materias)


_CUATRIMESTRES = {"primer": 1, "segundo": 2, "tercer": 3, "cuarto": 4, "quinto": 5, "sexto": 6, "septimo": 7,
                  "séptimo": 7, "octavo": 8, "noveno": 9, "decimo": 10, "décimo": 10}


def plan_fca_unju(texto: str) -> list[tuple[str, int]]:
    """UNJu Ciencias Agrarias' tecnicaturas (``-layout`` text): each term's
    heading ("PRIMER CUATRIMESTRE", ...) over a row per subject, its
    two-digit code first; a name the cell wrapped sits above and below its
    code's line ("ELEMENTOS DE MATEMÁTICA Y" / "01   4   60" / "ESTADÍSTICA"),
    or beside it. A term's year is half its number, rounded up; the
    "TOTAL DE HORAS" lines are not subjects."""
    lineas = texto.splitlines()
    materias: list[tuple[str, int]] = []
    cuatrimestre = None
    for numero, linea in enumerate(lineas):
        # ("A PARTIR DEL QUINTO CUATRIMESTRE": the practices of a tecnicatura's last term.)
        titulo = re.match(r"^\s*(?:A PARTIR DEL\s+)?(\w+)\s+CUATRIMESTRE\s*$", linea)
        if titulo and titulo.group(1).lower() in _CUATRIMESTRES:
            cuatrimestre = _CUATRIMESTRES[titulo.group(1).lower()]
            continue
        fila = re.match(r"^\s*(\d{2})(\s+)(.*?)(?:\s{2,}\d|\s*$)", linea)
        if not fila or not cuatrimestre:
            continue
        nombre = clean_text(fila.group(3))
        if not nombre or re.fullmatch(r"[\d\s,.-]+", nombre):
            piezas = []
            for vecina in (lineas[numero - 1] if numero else "", lineas[numero + 1] if numero + 1 < len(lineas) else ""):
                pieza = clean_text(re.split(r"\s{3,}", vecina.strip())[0]) if vecina.strip() else ""
                if pieza and not re.match(r"^\d", pieza) and not re.search(r"(?i)total de horas|cuatrimestre", pieza):
                    piezas.append(pieza)
            nombre = clean_text(" ".join(piezas))
        if nombre and not re.search(r"(?i)total de horas|^aprobad[oa]s?$", nombre):
            _agregar(materias, nombre, (cuatrimestre + 1) // 2)
    # A name cut short ("COMERCIALIZACIÓN: de la carne y el"): the table is not read.
    if any(re.search(r"(?i)\b(?:de|del|el|la|los|las|y|e|en|a|con|para)$", n) for n, _ in materias):
        return []
    return materias
plan_fca_unju.respaldo = True  # type: ignore[attr-defined]  # its licenciaturas go to the general reader


def plan_upe(ruta: str) -> list[tuple[str, int]]:
    """UPE's plan sheets: a row per subject, its number left of the names
    under "Asignatura" and its hours under "Horaria"; a name the cell wrapped
    sits above, beside and below its number ("Fundamentos de" / "7 la Cadena
    de" / "Suministros"), so each line of the names goes to the row whose
    number is nearest. The terms ("3° Cuatrimestre", level or turned on its
    side) sit in the margin, in a cell its rows' height that the table's
    rules close (``-bbox-layout`` gives the words, pdfplumber the rules): a
    row's term is the one whose label falls between the same two rules. A
    term's year is half its number, rounded up; "Gestión Logística l" is
    its roman "I"."""
    import subprocess

    import pdfplumber

    cajas = subprocess.run(["pdftotext", "-bbox-layout", ruta, "-"], capture_output=True,
                           text=True, timeout=60).stdout
    with pdfplumber.open(ruta) as pdf:
        reglas = {n: [(e["top"], e["x0"], e["x1"]) for e in pagina.horizontal_edges]
                  for n, pagina in enumerate(pdf.pages)}
    return plan_upe_de(cajas, reglas)
plan_upe.ruta = True  # type: ignore[attr-defined]


def plan_upe_de(cajas: str, reglas: dict[int, list[tuple[float, float, float]]]) -> list[tuple[str, int]]:
    """``plan_upe`` on the text's boxes and each page's horizontal rules (top, left, right)."""
    palabras = []
    for pagina, contenido in enumerate(re.findall(r"<page\b.*?</page>", cajas or "", re.S)):
        for x, y, x2, alto, texto in re.findall(
                r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">([^<]*)</word>', contenido):
            palabras.append((pagina, float(x), float(y), float(x2), float(alto), unicodedata.normalize("NFKC", texto)))
    asignatura = next((x for _, x, _, _, _, t in palabras if t == "Asignatura"), None)
    horaria = next((x for _, x, _, _, _, t in palabras if t == "Horaria"), None)
    if not asignatura or not horaria:
        return []
    # The rows' numbers, left of "Asignatura"; the names start right of the first.
    filas = sorted((p, y, int(t)) for p, x, y, _, _, t in palabras
                   if re.fullmatch(r"\d{1,2}", t) and asignatura - 45 <= x < asignatura - 10)
    if not filas or [n for _, _, n in filas] != list(range(1, len(filas) + 1)):
        return []
    izquierda = min(x for p, x, y, _, _, t in palabras if (p, y, t) == (filas[0][0], filas[0][1], "1")) + 10
    # The names' lines: words under "Asignatura", by their line.
    renglones: dict[tuple[int, int], list[tuple[float, str]]] = {}
    for p, x, y, _, _, t in palabras:
        if izquierda <= x < horaria - 3 and not re.fullmatch(r"\d+", t):
            renglones.setdefault((p, round(y)), []).append((x, t))
    nombres: dict[int, list[tuple[float, str]]] = {}
    for (p, y), piezas in renglones.items():
        cerca = min(((abs(fy - y), n) for fp, fy, n in filas if fp == p), default=None)
        if not cerca or cerca[0] > 22:
            continue
        nombres.setdefault(cerca[1], []).append((y, " ".join(t for _, t in sorted(piezas))))
    # The terms' labels ("Cuatrimestre" beside or above its "1°"): their left edge, halfway down.
    terminos = []
    for i, (p, x, y, x2, alto, t) in enumerate(palabras):
        numero = re.fullmatch(r"(\d)\s*[°º]", t)
        vecinas = [v for v in palabras[max(i - 1, 0):i + 2] if v[5].lower() == "cuatrimestre" and v[0] == p
                   and (abs(v[2] - y) < 3 and 0 < v[1] - x < 30 or abs(v[1] - x) < 3 and abs(v[2] - y) < 80)]
        if numero and vecinas and x < izquierda - 25:
            # Of two labels' words beside it, its own touches it.
            v = min(vecinas, key=lambda v: max(v[2] - alto, y - v[4], v[1] - x2, x - v[3], 0))
            terminos.append((p, min(x, v[1]) + 3, (min(y, v[2]) + max(alto, v[4])) / 2,
                             int(numero.group(1))))
    if sorted(c for *_, c in terminos) != list(range(1, len(terminos) + 1)) or not terminos:
        return []
    # Each label's cell: between the nearest rules above and below it that cross its column.
    tramos = []
    for p, x, y, c in terminos:
        cortes = [top for top, x0, x1 in reglas.get(p, []) if x0 <= x <= x1]
        arriba = max((top for top in cortes if top < y), default=None)
        abajo = min((top for top in cortes if top > y), default=None)
        if arriba is None or abajo is None:
            return []
        tramos.append((p, arriba, abajo, c))
    materias: list[tuple[str, int]] = []
    for p, y, numero in filas:
        suyo = [c for tp, arriba, abajo, c in tramos if tp == p and arriba < y < abajo]
        nombre = clean_text(" ".join(t for _, t in sorted(nombres.get(numero, []))))
        nombre = re.sub(r"\s(l{1,3}|lV|Vl{0,3})$", lambda m: " " + m.group(1).replace("l", "I"), nombre)
        if len(suyo) != 1 or not nombre:
            return []
        _agregar(materias, nombre, (suyo[0] + 1) // 2)
    return desde_el_primero(materias)


def plan_umendoza_pagina(html: str) -> list[tuple[str, int]]:
    """The UMendoza's career pages: the "Plan de estudio" tab, a heading per
    year ("1er Año", "2do Año") over a paragraph of its subjects, one a line,
    each marked how it is taught ("(s)", "(a)", "(p)"). A heading that is not
    a year ("CONDICIÓN FINAL DE EGRESO", "ÁREAS DE ORIENTACIÓN") ends the plan."""
    soup = BeautifulSoup(html or "", "html.parser")
    for panel in soup.select(".fl-tabs-panel-content"):
        materias: list[tuple[str, int]] = []
        anio = None
        for elemento in panel.find_all(["h2", "h3", "h4", "p"]):
            texto = clean_text(elemento.get_text(" "))
            if elemento.name != "p":
                if re.match(r"(?i)plan de estudios?\b", texto) and anio is None:
                    continue
                anio = anio_de(texto)
                if anio is None:
                    break
                continue
            if anio is None:
                continue
            for linea in elemento.get_text("\n").split("\n"):
                linea = re.sub(r"(?:\s*\([sapSAP]\))+\s*$", "", clean_text(linea))
                # (Diseño's years head their subjects with their cycle: "Ciclo de Información".)
                if linea and not re.fullmatch(r"(?i)ciclo de \w+", linea):
                    _agregar(materias, linea, anio)
        if materias:
            return desde_el_primero(materias)
    return []


def plan_fhu_unse(html: str) -> list[tuple[str, int]]:
    """The UNSE Humanidades' "Asignaturas" page of each career: the subjects
    under their years ("1º AÑO", "PRIMER AÑO"), maybe numbered in order
    ("12 - Obstetricia 1") and grouped in terms ("3º MODULO", not subjects).
    A page whose names run into each other ("Finanzas PúblicasIngl", its
    Contador's) is not read."""
    materias = []
    for nombre, anio in plan_por_anios(html):
        if re.fullmatch(r"(?i)\d+\s*[º°]\s*m[oó]dulo", nombre):
            continue
        nombre = re.sub(r"^\d{1,2}\s*[-–.]\s*", "", nombre)
        if re.search(r"[a-záéíóúñ][A-ZÁÉÍÓÚÑ]", nombre):
            return []
        _agregar(materias, nombre, anio)
    return desde_el_primero(materias)


_ANIO_AGRO_UBA = re.compile(r"(?i)\b(primer|segundo|tercer|cuarto|quinto|sexto)\s+año\b")


def plan_agro_uba(texto: str) -> list[tuple[str, int]]:
    """UBA Agronomía's plan sheets (``-layout``): a heading per year ("Primer
    Año (CBC)", "Ciclo Profesional – Segundo Año"), its two terms side by
    side, each subject "Name (credits)" with its prerequisites under it
    ("*Edafología"). A name the sheet wrapped (its credits alone on the next
    line, or a line that starts in lowercase) is not known whole, so the
    plan is not read; nor is a list of electives taken for a subject."""
    materias: list[tuple[str, int]] = []
    anio = None
    for linea in texto.splitlines():
        if re.match(r"(?i)\s*requisitos exigidos", linea):
            break
        for trozo in re.finditer(r"\S(?:.*?\S)?(?=\s{3,}|\s*$)", linea):
            pieza = trozo.group(0).strip()
            de_anio = _ANIO_AGRO_UBA.search(pieza)
            if de_anio and len(pieza) < 45:
                anio = ["primer", "segundo", "tercer", "cuarto", "quinto", "sexto"].index(de_anio.group(1).lower()) + 1
                continue
            if anio is None or pieza.startswith("*") or re.match(r"(?i)(primer|segundo)\s+cuatrimestre", pieza):
                continue
            if re.fullmatch(r"\(\d+(?:[.,]\d+)?\)", pieza):
                return []
            # (A tecnicatura's CBC subjects: "Cod 5. Química (6) CBC".)
            materia = re.fullmatch(r"(.+?)\s*\(\d+(?:[.,]\d+)?\)(?:\s+CBC)?", pieza)
            if materia:
                nombre = re.sub(r"(?i)^cod\.?\s*\d+\s*[-.]?\s*", "", materia.group(1))
                if nombre[0].islower() or re.match(r"(?i)asignaturas\b", nombre):
                    return []
                _agregar(materias, nombre, anio)
    return desde_el_primero(materias)


def plan_agrarias_unca(html: str, carrera: str) -> list[tuple[str, int]]:
    """UNCA Agrarias' one page of every career, each in a window headed by
    its name (then "×"): "Primer Año" ... over its subjects, each with its
    term ("Matemática I (1c)", "Computación (anual)"); "Instancias Finales"
    goes on in the last year. The window ends at its plans' links ("Plan de
    Estudio 2025") or at the next career's."""
    soup = BeautifulSoup(html or "", "html.parser")
    for basura in soup(["script", "style"]):
        basura.decompose()
    lineas = [clean_text(l).strip("​ ") for l in soup.get_text("\n").split("\n")]
    lineas = [l for l in lineas if l]
    clave = comparison_key(carrera)
    inicio = next((i for i in range(len(lineas) - 1)
                   if lineas[i + 1] == "×" and comparison_key(lineas[i]) == clave), None)
    if inicio is None:
        return []
    materias: list[tuple[str, int]] = []
    anio = None
    for linea in lineas[inicio + 2:]:
        if linea == "×" or linea == "Mas Información" or linea.startswith("Plan de Estudio"):
            break
        de_anio = anio_de(linea) if len(linea) < 30 else None
        if de_anio:
            anio = de_anio
            continue
        materia = re.fullmatch(r"(.+?)\s*\((?:\d\s*c|anual)\)", linea, re.I)
        if materia and anio:
            _agregar(materias, materia.group(1), anio)
    return desde_el_primero(materias)
plan_agrarias_unca.carrera = True  # type: ignore[attr-defined]


def plan_filo_unt_pagina(html: str, carrera: str) -> list[tuple[str, int]]:
    """UNT Filosofía y Letras' career pages: the Profesorado's and the
    Licenciatura's plans, each a <details> headed by its name ("Profesorado
    en Historia (Plan 2018)", maybe "32 materias"), a column per year ("1°"
    "AÑO") of its subjects; the first years both share may come before, out
    of either ("1° y 2° año · iguales en los dos títulos"). The career's is
    the one of its kind (Profesorado, Licenciatura) whose other words are the
    career's ("Profesorado de Historia"); one that does not hold as many
    subjects as its heading says is not read."""
    def palabras(nombre: str) -> tuple[str, frozenset[str]]:
        sin_plan = re.sub(r"\s*\(plan.*", "", nombre, flags=re.I)
        todas = re.findall(r"[a-z]+", comparison_key(sin_plan))
        return (todas[0] if todas else ""), frozenset(todas[1:]) - {"de", "en", "la", "el", "y", "con", "orientacion"}

    def columnas(raiz: Tag, fuera_de_details: bool) -> list[tuple[str, int]]:
        leidas = []
        # (Boxes as <div>, or as <span> on some pages: Francés.)
        for columna in raiz.find_all(["div", "span"]):
            hijos = columna.find_all(["div", "span"], recursive=False)
            encabezado = clean_text(hijos[0].get_text(" ")) if hijos else ""
            if not re.fullmatch(r"(?i)\d\s*°\s*año", encabezado) or (fuera_de_details and columna.find_parent("details")):
                continue
            for hijo in hijos[1:]:
                # (The subject's own box, or the name inside it.)
                nombre = clean_text((hijo.find(["div", "span"]) or hijo).get_text(" "))
                if nombre:
                    leidas.append((nombre, int(encabezado[0])))
        return leidas

    buscada = palabras(carrera)
    soup = BeautifulSoup(html or "", "html.parser")
    for detalle in soup.find_all("details"):
        resumen = detalle.find("summary")
        textos = [clean_text(d.get_text(" ")) for d in resumen.find_all("div")] if resumen else []
        # (The name's own box, not the one around it and its hours.)
        titulo = min((t for t in textos if re.match(r"(?i)(profesorado|licenciatura|tecnicatura)\b", t)),
                     key=len, default=None)
        cuantas = next((int(m.group(1)) for t in textos for m in [re.match(r"(\d+)\s+materias", t)] if m), None)
        if not titulo or palabras(titulo) != buscada:
            continue
        propias = columnas(detalle, False)
        if not propias or (cuantas and len(propias) != cuantas):
            return []
        materias: list[tuple[str, int]] = []
        for nombre, anio in columnas(soup, True) + propias:
            _agregar(materias, nombre, anio)
        return desde_el_primero(materias)
    return []
plan_filo_unt_pagina.carrera = True  # type: ignore[attr-defined]


def plan_udc(html: str, carrera: str) -> list[tuple[str, int]]:
    """The UDC's career pages: a toggle per year ("3er Año") listing its
    subjects. A page of a Licenciatura and the Tecnicatura it passes through
    marks what only one of them has: a whole year ("*Las siguientes materias
    son exclusivas de la Licenciatura*", "*solo Licenciatura*"), a term's list
    ("Segundo cuatrimestre Tecnicatura Universitaria") or a subject ("Trabajo
    final (sólo para la Tecnicatura)", "Taller de Mecánica (solo
    Tecnicatura)"): each career takes its own. When a workshop is taken goes
    ("Taller de Inglés I – 1er. cuatrimestre")."""
    def de_quien(texto: str) -> str | None:
        marca = re.search(r"(?i)\b(?:s[óo]lo(?: para la)?|exclusivas de la)\s+(tecnicatura|licenciatura)", texto)
        return marca.group(1).lower() if marca else None

    soup = BeautifulSoup(html or "", "html.parser")
    propia = "tecnicatura" if re.match(r"(?i)tecnicatura", carrera) else "licenciatura"
    materias: list[tuple[str, int]] = []
    for item in soup.select(".elementor-toggle-item"):
        titulo = item.select_one(".elementor-tab-title")
        contenido = item.select_one(".elementor-tab-content")
        anio = anio_de(clean_text(titulo.get_text(" "))) if titulo else None
        if not anio or not contenido:
            continue
        del_anio = None
        seccion = None
        # (A year of one subject gives it as a paragraph: "Trabajo Final – anual.")
        sin_lista = not contenido.find("li")
        for elemento in contenido.find_all(["p", "li"]):
            texto = clean_text(elemento.get_text(" "))
            if elemento.name == "p" and not (sin_lista and not texto.startswith("*")):
                # A heading of the year ("*solo Licenciatura*") or of a term's list.
                if re.match(r"(?i)\*", texto) and de_quien(texto):
                    del_anio = de_quien(texto)
                elif re.match(r"(?i)(primer|segundo)\s+cuatrimestre|anual", texto):
                    seccion = next((k for k in ("tecnicatura", "licenciatura") if k in texto.lower()), None)
                continue
            duenia = de_quien(texto) or seccion or del_anio
            if duenia and duenia != propia:
                continue
            nombre = re.sub(r"(?i)\s*\(\s*s[óo]lo(?: para la)? \w+\s*\)", "", texto)
            nombre = re.sub(r"\s+[–-]\s+(?:\d\w*\.?\s+cuatrimestre|anual)\.?$", "", nombre, flags=re.I)
            _agregar(materias, nombre, anio)
    return desde_el_primero(materias)
plan_udc.carrera = True  # type: ignore[attr-defined]


_ANIO_CBA = re.compile(r"(?i)^\s*(.*?):?\s*(\d)\s*[º°o]\s*:?\s*AÑO\s*$")
_TOTAL_CBA = re.compile(r"(?i)^\s*total\s*:?\s*(\d+)\s+(?:unidades\s+curriculares|UC)\b:?\s*(\d+)?")
# A row's hours: weekly, yearly and the Taller Integrador's ("4 128 0 4",
# "34h 1088h 3h 37h", "2*" with a footnote); what comes before them is the
# unit's name, if any.
_HORAS_CBA = re.compile(r"(?<!\S)\d+\s?[h*]?\s{2,}\d+\s?[h*]?\s{2,}\d+\s?[h*]?(?!\S)")


def plan_cordoba(encabezado: str, texto: str) -> list[tuple[str, int]]:
    """A design of Córdoba's Dirección General de Educación Superior: a page
    per year headed "PROFESORADO DE EDUCACIÓN SECUNDARIA EN MATEMÁTICA: 1º
    AÑO", a row per unit with its hours (a name too long for its column
    wraps above and below the row: "Práctica Docente III: / El Aula: Espacio
    del Aprender y del  5 160 1 6 / Enseñar"), and "Total: 7 Unidades
    Curriculares" closing it. Only the years whose heading ``encabezado``
    matches (one document holds Inicial and Primaria), and only when every
    year has as many units as its total says: else nothing."""
    materias: list[tuple[str, int]] = []
    anio = 0
    bloque: list[str] = []
    del_anio: list[str] = []
    horas_del_anio: list[int] = []

    def cerrar_bloque(lineas: list[str] | None = None) -> None:
        # Rows not parted by a blank line share a block. A name's wrapped lines
        # go with the row above them, unless the next row has no name of its
        # own (its hours sit midway down the name: "Estudios Socioculturales y
        # Literarios / 4 128 0 4 / de Pueblos de Habla Inglesa I").
        lineas = bloque if lineas is None else lineas
        horas = [_HORAS_CBA.search(l) for l in lineas]
        if not any(horas):
            return
        horas_del_anio.extend(int(re.match(r"\d+", h.group()).group()) for h in horas if h)
        corte = min(h.start() for h in horas if h)
        # A unit made of parts: its name at the left edge, each part indented
        # beside or under it, with its own format ("Ciencias   Educación para
        # la Salud / Naturales / Educación Ambiental"). Each part is a unit of
        # the year's total; the name over them is not. The rows before and
        # after the parts are read as any.
        nombres = [linea[:corte].rstrip() for linea in lineas]
        partes = [i for i, n in enumerate(nombres) if re.search(r"(?:^|\s{2})\s{6,}\S", n) and re.search(r"\S", n[:8])
                  or re.match(r"\s{8,}\S", n)]
        if partes and any(re.match(r"\S", n) for n in nombres[partes[0]:partes[-1] + 1]):
            cerrar_bloque(lineas[:partes[0]])
            for nombre in nombres[partes[0]:partes[-1] + 1]:
                del_anio.extend(m.group() for m in re.finditer(r"\S+(?: \S+)*", nombre) if m.start() >= 8)
            cerrar_bloque(lineas[partes[-1] + 1:])
            return
        filas: list[list[str]] = []
        sueltas: list[str] = []
        for linea, h in zip(lineas, horas):
            parte = linea[:corte].strip()
            if h:
                propio = linea[:h.start()].strip()
                if propio:
                    if filas:
                        filas[-1] += sueltas
                    else:
                        propio = " ".join(sueltas + [propio])
                    filas.append([propio])
                else:
                    # What begins in lower case or in brackets still ends the
                    # name above ("de Pueblos de Habla Inglesa II",
                    # "(guitarra/piano)").
                    while filas and sueltas and (sueltas[0][:1].islower() or sueltas[0][:1] == "("):
                        filas[-1].append(sueltas.pop(0))
                    filas.append(sueltas[:])
                sueltas = []
            elif parte:
                sueltas.append(parte)
        if filas:
            filas[-1] += sueltas
        for partes_del_nombre in filas:
            # Without a footnote's mark ("Taller de Ciencias en la Escuela *").
            nombre = re.sub(r"\s+", " ", " ".join(partes_del_nombre)).strip(" *")
            if nombre and not re.match(r"(?i)campo de la|total\b", nombre):
                del_anio.append(nombre)

    for linea in texto.splitlines():
        linea = linea.replace("\f", "")
        cabeza = _ANIO_CBA.match(linea)
        if cabeza and "…" not in linea and "..." not in linea:
            bloque, del_anio, horas_del_anio[:] = [], [], []
            anio = int(cabeza.group(2)) if re.search(encabezado, cabeza.group(1), re.I) else 0
            continue
        if not anio:
            continue
        total = _TOTAL_CBA.match(linea)
        if total:
            cerrar_bloque()
            # A total that miscounts its units still adds up its weekly hours
            # (Física's 4th year: "Total: 6", seven units of 32 hours).
            if len(del_anio) != int(total.group(1)) and not (
                    total.group(2) and sum(horas_del_anio) == int(total.group(2))):
                return []
            materias += [(n, anio) for n in del_anio]
            anio, bloque, del_anio = 0, [], []
            horas_del_anio.clear()
            continue
        if not linea.strip():
            cerrar_bloque()
            bloque = []
        elif re.match(r"(?i)^\s*campo(s)? de la|^\s*hs\.|^\s*diseño curricular de la provincia", linea):
            cerrar_bloque()
            bloque = []
        else:
            bloque.append(linea)
    # Every year from the first, or the plan is not whole; and every name as
    # the design writes it (where it presents each unit), or a row was joined
    # to the next one ("TIC y su enseñanza en DI Comunicación y Trastornos del").
    anios = {a for _, a in materias}
    if not anios or anios != set(range(1, max(anios) + 1)):
        return []
    # A name whose table cell shares its line with the format ("Práctica
    # Docente IV y Residencia: / Recrear las Prácticas Docentes") is found by
    # its two halves.
    plano = " " + " ".join(re.findall(r"[a-z0-9]+", comparison_key(texto))) + " "
    for nombre, _ in materias:
        for mitad in nombre.split(": "):
            if " " + " ".join(re.findall(r"[a-z0-9]+", comparison_key(mitad))) + " " not in plano:
                return []
    return materias


_CODIGO_IFTS = re.compile(r"(?<![\d.])([1-4])\.([1-8])\.(\d{1,2})\.?(?=\s|$)")
_CUATRIMESTRE_IFTS = re.compile(r"\d\s*°\s*/\s*\d\s*°")
# A row's data: its field, format and term, then its hours ("FTE  MO  C  9  6
# 96", "M  C  4.5  -  112").
_DATOS_IFTS = re.compile(r"\s{2,}(?:(?:[A-Z][A-Za-z]{0,3}|Materia|Taller|Seminario|Asignatura|M[óo]dulo|Laboratorio|Proyecto)\s+){1,3}"
                         r"(?:\d+(?:[.,]\d+)?|-)(?:\s+(?:\d+(?:[.,]\d+)?|-)){1,4}\s*$")
_ENCABEZADO_IFTS = re.compile(r"(?i)^(?:primer|segundo|tercer|cuarto)\s+a[ñn]o\b|cuatrimestre$|^(?:\d\s*°?\s*)?(?:sem|cuat|cuatrim)\.?$"
                              r"|^(?:c[óo]digo|denominaci[óo]n|totales|unidad curricular|rimestre|a[ñn]o)\b")
_SIN_TERMINAR_IFTS = re.compile(r"(?i)\b(?:de|del|y|e|o|u|el|la|las|los|en|a|al|para|por|con|sobre)$")


def plan_codigos_ifts(texto_con_columnas: str) -> list[tuple[str, int]]:
    """The plan of a CABA IFTS career (the PDF the Agencia de Aprendizaje's
    record links): a row per unit with its code (year, term, number: "1.2.3"),
    its name and its data ("FTE  MO  C  9  6  96"). A name too long for its
    cell is centred on the row's data: as many lines above it as below
    ("Protocolo de Internet de las / 1.2.2  FE Mo C 6 4 64 / Cosas"), the code
    on the data's line or next to it. Nothing unless every term numbers its
    units from 1 without a gap, every year from the first is there, every
    line of name has one row to go with, and no name is left unfinished."""
    lineas = [_CUATRIMESTRE_IFTS.sub(lambda m: " " * len(m.group()), l.replace("\u200b", ""))
              for l in texto_con_columnas.splitlines()]
    datos, nombres, codigos = set(), {}, {}
    for i, linea in enumerate(lineas):
        fila = _DATOS_IFTS.search(linea)
        izquierda = linea[:fila.start()] if fila else linea
        codigo = _CODIGO_IFTS.search(izquierda)
        # (Beside the code, the year's and term's label of a merged cell:
        # "2° año 1er", "Cuatrim".)
        if codigo and re.fullmatch(r"(?i)[\s\d°º/]*(?:(?:a[ñn]o|cuatrim\w*|er|do|ro|to)\b[\s\d°º/.]*)*",
                                   izquierda[:codigo.start()]):
            codigos[i] = (int(codigo.group(1)), int(codigo.group(2)), int(codigo.group(3)))
            izquierda = " " * codigo.end() + izquierda[codigo.end():]
            # A coded row whose hours went to the next line ("MO  C   96").
            if not fila:
                fila = re.search(r"\s{2,}(?:[A-Z][A-Za-z]{0,3}\s+){1,3}", izquierda)
                izquierda = izquierda[:fila.start()] if fila else izquierda
        if fila:
            datos.add(i)
        # The name's part of a line, not the hours that went to it ("Objetos   4  -").
        texto = re.split(r"\s{3,}", izquierda.strip())[0]
        if texto and not _ENCABEZADO_IFTS.search(texto) and re.match(r"[A-ZÁÉÍÓÚÑa-záéíóúñ(]", texto):
            nombres[i] = texto
    unidades: list[dict[str, Any]] = []
    for d in sorted(datos):
        codigo = codigos.get(d) or codigos.get(d + 1) or codigos.get(d - 1)
        if not codigo:
            if unidades:
                break  # the table is over: a later table's rows
            continue
        unidades.append({"d": d, "codigo": codigo, "lineas": []})
    if not unidades or len({u["codigo"] for u in unidades}) != len(unidades):
        return []
    libres = {i for i in nombres if unidades[0]["d"] - 2 <= i <= unidades[-1]["d"] + 3}
    for unidad in unidades:
        if unidad["d"] in libres:
            unidad["lineas"].append(unidad["d"])
            libres.discard(unidad["d"])
    for distancia in (1, 2):
        for unidad in unidades:
            arriba, abajo = unidad["d"] - distancia, unidad["d"] + distancia
            if arriba in libres and abajo in libres:
                unidad["lineas"] += [arriba, abajo]
                libres -= {arriba, abajo}
    for i in sorted(libres):
        cerca = sorted(unidades, key=lambda u: abs(u["d"] - i))
        if abs(cerca[0]["d"] - i) > 2 or (len(cerca) > 1 and abs(cerca[1]["d"] - i) == abs(cerca[0]["d"] - i)):
            return []  # a line of name no row clearly owns
        cerca[0]["lineas"].append(i)
    materias: list[tuple[str, int]] = []
    numeros: dict[tuple[int, int], list[int]] = {}
    for unidad in unidades:
        nombre = " ".join(" ".join(nombres[i] for i in sorted(unidad["lineas"])).split())
        if not nombre or _SIN_TERMINAR_IFTS.search(nombre):
            return []
        anio, cuatrimestre, numero = unidad["codigo"]
        numeros.setdefault((anio, cuatrimestre), []).append(numero)
        materias.append((nombre, anio))
    if any(sorted(n) != list(range(1, len(n) + 1)) for n in numeros.values()):
        return []
    anios = {anio for anio, _ in numeros}
    return materias if anios == set(range(1, max(anios) + 1)) else []


_FILA_NUMERADA_IFTS = re.compile(r"^\s*(\d{2})\s+([1-4])\s+([1-8])\s+(\S.*)$")


def plan_numerado_ifts(texto_con_columnas: str) -> list[tuple[str, int]]:
    """An IFTS plan whose rows give a number, the year and the term before
    the name ("05   1   1   Cuidado de enfermería   M  C  10  160 ..."), the
    rest of a long name in the lines below, in its column ("en la familia y
    / comunidad"). Nothing unless the rows are numbered from 01 without a
    gap, every year from the first is there and no name is left unfinished."""
    filas: list[dict[str, Any]] = []
    columna = None
    for linea in texto_con_columnas.splitlines():
        fila = _FILA_NUMERADA_IFTS.match(linea)
        if fila:
            columna = fila.start(4)
            filas.append({"numero": int(fila.group(1)), "anio": int(fila.group(2)),
                          "partes": [re.split(r"\s{2,}", fila.group(4).strip())[0]]})
            continue
        if not linea.strip():
            if filas:
                filas[-1]["cerrada"] = True
            continue
        if filas and columna is not None and not filas[-1].get("cerrada"):
            inicio = len(linea) - len(linea.lstrip())
            if abs(inicio - columna) <= 2:
                filas[-1]["partes"].append(re.split(r"\s{2,}", linea.strip())[0])
    if not filas or [f["numero"] for f in filas] != list(range(1, len(filas) + 1)):
        return []
    materias = []
    for fila in filas:
        nombre = " ".join(" ".join(fila["partes"]).split())
        if _SIN_TERMINAR_IFTS.search(nombre):
            return []
        # A unit and its practice under one name (Enfermería's two "Gestión y
        # Administración en Enfermería") is one subject.
        if comparison_key(nombre) not in {comparison_key(n) for n, _ in materias}:
            materias.append((nombre, fila["anio"]))
    anios = {anio for _, anio in materias}
    return materias if anios == set(range(1, max(anios) + 1)) else []


_FILA_UNRN = re.compile(r"^\s*([A-Z]{1,3}\d{3,4})\s+(\d{1,2})(?:\s*\(\*t\))?(?:\s+([^\d\s–-].*?))?(?:\s{2,}[\d–-].*)?\s*$")


def plan_unrn(texto: str) -> list[tuple[str, int]]:
    """UNRN's career sheets ("FICHA DE CARRERA", ``-layout``): under "PLAN DE
    ESTUDIOS", a heading per year ("PRIMER AÑO", "1º AÑO") and a row per
    subject: its SIU Guaraní code, its order number (an intermediate degree's
    marked "(*t)"), its name and its hours. A name the cell wrapped is a line
    of text alone beside its row: it belongs to the row after it when that
    row has no name of its own ("Solución de controversias..." / "VR328 29"
    / "aplicado"), else to the row before ("T0002 2 Introducción a la
    Lectura y Escritura" / "Académica"). The order numbers run 1, 2, 3...: a
    gap is a row not read, and then the plan is not."""
    lineas = texto.splitlines()
    inicio = next((i for i, l in enumerate(lineas) if re.match(r"\s*PLAN DE ESTUDIOS?\s*$", l)), None)
    if inicio is None:
        return []
    filas: list[list] = []  # [line index, order, name pieces, year]
    sueltas: list[tuple[int, str]] = []
    anio = None
    for i in range(inicio + 1, len(lineas)):
        linea = lineas[i].strip()
        if not linea:
            continue
        fila = _FILA_UNRN.match(lineas[i])
        if fila:
            if anio is None:
                return []
            filas.append([i, int(fila.group(2)), [fila.group(3)] if fila.group(3) else [], anio, bool(fila.group(3))])
            continue
        de_anio = anio_de(linea) if len(linea) < 25 else None
        if de_anio:
            anio = de_anio
            continue
        # (The sheet's notes after the table: "TITULO: AUXILIAR UNIVERSITARIO/A...".)
        if re.match(r"(?i)t[íi]tulo\b|certificaci[óo]n|observaciones|referencias", linea):
            break
        if re.match(r"(?i)(primer|segundo)\s+cuatrimestre|anual$|subtotal|total|carga\s+horaria|n°\s*orden", linea) \
                or re.fullmatch(r"[\d\s–\-/.,]+", linea):
            continue
        if anio is not None and not re.search(r"\s{3,}", linea):
            sueltas.append((i, linea))
    if not filas or [f[1] for f in filas] != list(range(1, len(filas) + 1)):
        return []
    for i, texto_suelto in sueltas:
        siguiente = next((f for f in filas if f[0] > i), None)
        anterior = next((f for f in reversed(filas) if f[0] < i), None)
        if siguiente and not siguiente[4] and siguiente[0] - i <= 2:
            siguiente[2].append(texto_suelto)
        elif anterior and i - anterior[0] <= 3:
            anterior[2].append(texto_suelto)
    materias: list[tuple[str, int]] = []
    for _, _, piezas, anio_fila, _ in filas:
        if not piezas:
            return []
        # (A heading of the table run into a name: "Inglés - Comprensión Lectora I ANUALES".)
        _agregar(materias, re.sub(r"\s+(?:ANUALES|ANUAL|CUATRIMESTRALES)$", "", " ".join(piezas)), anio_fila)
    return desde_el_primero(materias)


_ANIO_CUATRIMESTRE_IFTS = re.compile(r"(?i)^\s*(primer|segundo|tercer|cuarto)\s+a[ñn]o\s*[-–]\s*\w+\s+cuatrimestre\s*$")
# A row's data without its field: format and term, or only its hours ("M  C  4  64", "6   96").
_DATOS_SIN_CAMPO_IFTS = re.compile(r"\s{2,}(?:(?:[A-Z]{1,2}|Cuatrimestral|Anual|Materia|Taller|Seminario|Asignatura|M[óo]dulo)\s+){0,3}"
                                   r"\d+(?:[.,]\d+)?(?:\s+\d+(?:[.,]\d+)?){1,3}\s*$")


def plan_anio_cuatrimestre_ifts(texto_con_columnas: str) -> list[tuple[str, int]]:
    """An IFTS plan by "PRIMER AÑO - PRIMER CUATRIMESTRE" headings over rows
    of a name and its data ("Ergonomía   M  C  4  64", "Transporte  6  96").
    A name too long for its cell goes around its row's data: the line above
    and the line below ("Principios de Economía y Costos para la Higiene y /
    M C 4 64 / Seguridad"). Nothing unless every year from the first is
    there, every line of name goes with a row and no name is unfinished."""
    filas: list[dict[str, Any]] = []
    anio = 0
    sueltas: list[str] = []  # the lines of name above a row that has none
    for linea in texto_con_columnas.replace("\u200b", "").splitlines():
        if not linea.strip():
            continue
        encabezado = _ANIO_CUATRIMESTRE_IFTS.match(linea)
        if encabezado:
            if sueltas:
                return []
            anio = _ORDINALES[encabezado.group(1).lower()]
            continue
        if not anio:
            continue
        datos = _DATOS_SIN_CAMPO_IFTS.search(linea)
        nombre = " ".join((linea[:datos.start()] if datos else linea).split())
        if datos:
            if nombre and sueltas:
                return []
            filas.append({"anio": anio, "partes": sueltas + ([nombre] if nombre else []),
                          "abierta": not nombre})
            sueltas = []
        elif re.match(r"[A-ZÁÉÍÓÚÑa-záéíóúñ(]", nombre):
            previa = filas[-1] if filas else None
            if previa and (previa.pop("abierta", False) or _SIN_TERMINAR_IFTS.search(" ".join(previa["partes"]))
                           or nombre[0].islower()):
                previa["partes"].append(nombre)
            else:
                sueltas.append(nombre)
        else:
            break  # the table is over
    if sueltas or not filas:
        return []
    materias: list[tuple[str, int]] = []
    for fila in filas:
        nombre = " ".join(" ".join(fila["partes"]).split())
        if not nombre or _SIN_TERMINAR_IFTS.search(nombre):
            return []
        if comparison_key(nombre) not in {comparison_key(n) for n, _ in materias}:
            materias.append((nombre, fila["anio"]))
    anios = {a for _, a in materias}
    return materias if anios == set(range(1, max(anios) + 1)) else []
plan_unrn.respaldo = True  # type: ignore[attr-defined]  # its other sheets go to the general reader


# A row's data in an IFTS table without years: its format and régimen, if
# given, and its hours ("Materia cuatrimestral   6   0   96", "C   6   96").
_DATOS_INSTANCIA_IFTS = re.compile(
    r"\s{2,}(?:(?:Materia|Taller|Seminario|Asignatura|M[óo]dulo|Laboratorio|Proyecto|Pr[áa]ctica|[A-Z]{1,2}|"
    r"[Cc]uatrimestral|[Aa]nual|[Bb]imestral)\s+){0,3}(?:\d+(?:[.,]\d+)?|-)(?:\s+(?:\d+(?:[.,]\d+)?|-)){0,4}\s*$")
_FIN_DE_TABLA_IFTS = re.compile(r"(?i)^\s*(?:total|correlativ|requisit|perfil|●|alcances|t[íi]tulo)")
_ROTULO_IFTS = re.compile(r"(?i)^(?:campo|[áa]rea)\s+de\s+(?:la\s+)?formaci|^(?:primer|segundo|tercer)\s+(?:a[ñn]o|cuatrimestre)$")


def plan_instancias_ifts(texto_con_columnas: str) -> list[tuple[str, None]]:
    """An IFTS plan that lists its units without years: a row per unit, its
    name, then its format, régimen and hours ("Ecología General   Materia
    Cuatrimestral   5"), under its area's label at the left or a "Campo de
    la Formación ..." heading. The label is not a unit; a name too long for
    its cell goes on in the line below, or around a row of only data. The
    year is not given, so none is."""
    lineas = texto_con_columnas.replace("​", "").splitlines()
    inicio = next((i for i, l in enumerate(lineas) if re.search(r"(?i)contenidos", l)), None)
    if inicio is None:
        return []
    filas: list[dict[str, Any]] = []
    columna = None
    sueltas: list[str] = []
    for linea in lineas[inicio + 1:]:
        if not linea.strip():
            continue
        if filas and _FIN_DE_TABLA_IFTS.match(linea):
            break
        datos = _DATOS_INSTANCIA_IFTS.search(linea)
        izquierda = linea[:datos.start()] if datos else linea
        partes = [(m.start(), m.group()) for m in re.finditer(r"\S+(?: \S+)*", izquierda)]
        # The name is the last cell before the data; the area's label left of it is not.
        pieza = partes[-1] if partes else None
        if pieza and (_ROTULO_IFTS.search(pieza[1]) or not re.match(r"[A-ZÁÉÍÓÚÑa-záéíóúñ(]", pieza[1])):
            pieza = None
        if datos:
            if pieza and columna is None:
                columna = pieza[0]
            if pieza and abs(pieza[0] - columna) > 4:
                pieza = None
            filas.append({"partes": sueltas + ([pieza[1]] if pieza else []), "abierta": not pieza})
            sueltas = []
        elif pieza and columna is not None and abs(pieza[0] - columna) <= 4:
            previa = filas[-1] if filas else None
            if previa and (previa.pop("abierta", False) or pieza[1][0].islower()
                           or _SIN_TERMINAR_IFTS.search(" ".join(previa["partes"]))):
                previa["partes"].append(pieza[1])
            else:
                sueltas.append(pieza[1])
    if sueltas or len(filas) < 10:
        return []
    materias: list[tuple[str, None]] = []
    for fila in filas:
        # Without a footnote's mark: "Derecho Penal Tributario (*)".
        nombre = re.sub(r"(?:\s*\(\*\))+$", "", " ".join(" ".join(fila["partes"]).split()))
        if not nombre or _SIN_TERMINAR_IFTS.search(nombre):
            return []
        if comparison_key(nombre) not in {comparison_key(n) for n, _ in materias}:
            materias.append((nombre, None))
    return materias


def nombres_en_celdas(materias: list[tuple[str, Any]], texto_sin_columnas: str) -> bool:
    """Whether each name is a whole cell of the document as ``pdftotext``
    reads it without its columns (a cell's lines one after another): a
    name made of two cells' pieces ("Iluminación, Domótica y Eficiencia
    Energética Sistemas ...") or of a label and a cell ("CAMPO DE LA
    PRÁCTICA PROFESIONALIZANTE PP 1: ...") is not, nor one that begins in
    lower case (the end of another name)."""
    celdas = _celdas(texto_sin_columnas)
    return all(nombre[:1].isupper() and not re.search(r"\b[A-ZÁÉÍÓÚÑ]{4,}\s+[A-ZÁÉÍÓÚÑ]{2,}\s+[A-ZÁÉÍÓÚÑ]{2,}", nombre)
               and _clave_de_celda(nombre) in celdas for nombre, _ in materias)


def _clave_de_celda(texto: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", comparison_key(texto)))


def _celdas(texto_sin_columnas: str) -> set[str]:
    """Every run of one to seven lines of the document read without its
    columns, where a table's cell comes out whole."""
    lineas = [_clave_de_celda(l) for l in texto_sin_columnas.replace("​", "").splitlines()]
    # Without a row's code before its name: "FE10 Base de Datos".
    lineas = [re.sub(r"^[a-z]{1,2}\d{1,2} (?=[a-z])", "", l) for l in lineas if l]
    return {" ".join(lineas[i:i + n]) for i in range(len(lineas)) for n in range(1, 8)}


# What a row of an IFTS table says besides its unit's name: its format,
# régimen, field of training and hours.
_PALABRA_DE_DATOS_IFTS = re.compile(
    r"(?i)^(?:materia|taller|seminario|asignatura|m[óo]dulo|laboratorio|proyecto|pr[áa]cticas?|profesional(?:izante)?|"
    r"cuatrimestral|anual|bimestral|acreditable|op\.?|optativ[oa]|general|fundamentos?|fundamental|espec[íi]fic[oa]|"
    r"m|l|t|s|c|a|p|pp|tp|hc|-|–|\d+(?:[.,]\d+)?)$")
_CODIGO_DE_FILA_IFTS = re.compile(r"^(?:\d{1,2}|\d[.,]\d[.,]\d{1,2}\.?|[A-Z]{1,2}\d{1,2}|\d°(?:/\d°)?|[IVX]+)$")
_CABECERA_IFTS = re.compile(
    r"(?i)curricular|cursada|r[ée]gimen|formativ|denominaci|\bhs\b|hs\.|c[áa]t\.|\bsem\b|\btotal|c[óo]d(?:igo|\.)|"
    r"\bcuat\b|formato|duraci[óo]n|carga horaria|trab\b|aut[óo]n|^n°|estructura curricular")
_SECCION_IFTS = re.compile(r"(?i)^(?:(?:primer|segundo|tercer|cuarto)\s+(?:a[ñn]o|cuatrimestre)|\d(?:er|do|ro|to)\s+cuatrimestre|"
                           r"(?:campo|[áa]rea)\s+de\s+(?:la\s+)?formaci.*)$")
_HORAS_DECLARADAS = re.compile(r"(?i)cantidad de horas:\s*([\d.]+)\s*(?:horas?|hs\.?)\s*c[áa]t")


def _celdas_de(linea: str) -> list[tuple[int, str]]:
    return [(m.start(), m.group()) for m in re.finditer(r"\S+(?: \S+)*", linea)]


_RECORTABLE = "\x01"


def _nombre_de_celda(partes: list[str], celdas: set[str]) -> str | None:
    """The name a row's lines make that is a whole cell of the document,
    leaving out at the start of a line that began left of the names (marked
    ``_RECORTABLE``) the words of an area's label the columns ran into it
    ("formación Derecho privado"): the fewest words left out; none when two
    ways leave out as few."""
    import itertools

    opciones = [[" ".join(p.lstrip(_RECORTABLE).split()[k:]) for k in range(len(p.split()) + 1)]
                if p.startswith(_RECORTABLE) else [p] for p in partes]
    if math.prod(len(o) for o in opciones) > 5000:
        return None
    halladas: dict[int, set[str]] = {}
    for eleccion in itertools.product(*[range(len(o)) for o in opciones]):
        nombre = " ".join(o[k] for o, k in zip(opciones, eleccion) if o[k])
        if nombre and _clave_de_celda(nombre) in celdas:
            halladas.setdefault(sum(eleccion), set()).add(nombre)
    if not halladas:
        return None
    mejores = halladas[min(halladas)]
    return next(iter(mejores)) if len(mejores) == 1 else None


def plan_horas_ifts(texto_con_columnas: str, texto_sin_columnas: str = "") -> list[tuple[str, int | None]]:
    """An IFTS plan whose table gives each unit's hours, read whatever its
    columns: an area's label or a row's number and code at the left, the
    name, then its format, régimen, field and hours. A name too long for its
    cell wraps under it or around its row: within a group of lines between
    blank lines with a single row, all its lines are that row's; otherwise
    each goes to the nearest row. A line as near to the row above as to the
    one below goes where both rows' names come out as whole cells of the
    document read without its columns (``_celdas``); when neither way or both
    do, the plan is left unread. The plan is taken only when the rows' hours (each row's largest
    number) add up to the "Cantidad de horas: N horas cátedra" it declares,
    so that no row is missing and none is read twice. The year is the code's
    first figure ("2.1.3") when every row has one."""
    texto = texto_con_columnas.replace("​", "")
    declaradas = _HORAS_DECLARADAS.search(texto)
    inicio = re.search(r"(?i)contenidos", texto)
    if not declaradas or not inicio:
        return []
    return _tabla_por_horas(texto[inicio.end():], int(declaradas.group(1).replace(".", "")), texto_sin_columnas)



def _tabla_por_horas(texto: str, total_declarado: int, texto_sin_columnas: str,
                     minimo: int = 10) -> list[tuple[str, int | None]]:
    """The rows of a table that gives each unit's hours (``plan_horas_ifts``),
    when their hours add up to ``total_declarado``."""
    filas: list[dict[str, Any]] = []
    dudosas: list[tuple[int, str, list[dict[str, Any]]]] = []
    enteras = _celdas(texto_sin_columnas) if texto_sin_columnas else set()
    comienzos_de_celdas = {" ".join(c.split()[:n]) for c in enteras for n in range(1, len(c.split()) + 1)}
    for pagina in texto.split("\f"):
        # A name the page break cut goes on at the top of the next page.
        de_la_pagina_anterior = filas[-1] if filas else None
        lineas = pagina.splitlines()
        analizadas = []
        for i, linea in enumerate(lineas):
            # A code joined to its name by one space: "FG01 Redacción de Informes".
            celdas = []
            for comienzo, celda in _celdas_de(linea):
                pegado = re.match(r"([A-Z]{1,2}\d{1,2}|\d[.,]\d[.,]\d{1,2}\.?) (?=\S)", celda)
                if pegado and not celdas:
                    celdas += [(comienzo, pegado.group(1)), (comienzo + pegado.end(), celda[pegado.end():])]
                else:
                    celdas.append((comienzo, celda))
            def es_dato(celda: str) -> bool:
                return all(_PALABRA_DE_DATOS_IFTS.match(p) for p in celda.split())

            # The row's number and code at the left, perhaps after an area's
            # label ("Comunicación   10   Taller ..."): only when a name
            # follows them, not hours alone.
            codigos = []
            for desde in (0, 1):
                hasta = desde
                while hasta < len(celdas) and _CODIGO_DE_FILA_IFTS.match(celdas[hasta][1]) and hasta - desde < 4:
                    hasta += 1
                # A code that is not a bare number ("E1", "1.2.3") is one even
                # when its name sits on the lines around its row.
                if hasta > desde and hasta < len(celdas) and (desde == 0 or not es_dato(celdas[0][1])) \
                        and (not es_dato(celdas[hasta][1])
                             or any(not c.isdigit() for _, c in celdas[desde:hasta])):
                    codigos = celdas[desde:hasta]
                    celdas = celdas[hasta:]
                    break
            datos_desde = len(celdas)
            while datos_desde > 0 and es_dato(celdas[datos_desde - 1][1]):
                datos_desde -= 1
            datos = " ".join(c for _, c in celdas[datos_desde:])
            numeros = [float(n.replace(",", ".")) for n in re.findall(r"\d+(?:[.,]\d+)?", datos)]
            es_fila = bool(numeros) and (len(numeros) >= 2 or re.search(r"[A-Za-z]", datos)) \
                and re.search(r"\d+(?:\s*HC)?\s*$", linea.rstrip(" -–"))
            analizadas.append({"i": i, "codigos": codigos, "nombre": celdas[:datos_desde], "fila": bool(es_fila),
                               "horas": max(numeros) if es_fila else 0, "datos_en": celdas[datos_desde][0]
                               if es_fila and datos_desde < len(celdas) else None, "vacia": not linea.strip()})
        primera = next((a["i"] for a in analizadas if a["fila"]), None)
        if primera is None:
            continue
        # The table's heading, above its first row on each page, is not a name.
        cabecera = max((a["i"] for a in analizadas if a["i"] < primera and not a["vacia"]
                        and _CABECERA_IFTS.search(lineas[a["i"]])), default=-1)
        sin_codigo = not any(a["codigos"] for a in analizadas if a["fila"])
        comienzos = Counter(a["nombre"][-1][0] for a in analizadas if a["fila"] and a["nombre"])
        columna = comienzos.most_common(1)[0][0] if comienzos else None
        fin_de_nombres = min((a["datos_en"] for a in analizadas if a["fila"] and a["datos_en"]), default=10 ** 6)
        for a in analizadas:
            if a["i"] <= cabecera or a["vacia"]:
                a["partes"] = []
                continue
            piezas = [c for c in a["nombre"] if c[0] < fin_de_nombres or a["fila"]]
            if sin_codigo and columna is not None:
                # The area's label sits left of the names; a label joined to
                # a name by one space is cut where the names begin.
                recortadas = []
                for comienzo, celda in piezas:
                    if comienzo >= columna - 2:
                        recortadas.append(celda)
                    elif comienzo + len(celda) > columna and lineas[a["i"]][columna - 1:columna] == " ":
                        # Marked: the label's words may still begin it.
                        recortadas.append(_RECORTABLE + celda)
                piezas = [(0, c) for c in recortadas if c]
            if len(piezas) > 1:
                piezas = piezas[-1:]
            texto_nombre = piezas[0][1] if piezas else ""
            # A year's or term's label alone ("2°/1°") is not a name.
            if _CODIGO_DE_FILA_IFTS.match(texto_nombre.lstrip(_RECORTABLE)) \
                    and not re.fullmatch(r"[IVX]+", texto_nombre.lstrip(_RECORTABLE)):
                texto_nombre = ""
            if texto_nombre and (_SECCION_IFTS.match(texto_nombre.lstrip(_RECORTABLE))
                                 or _CABECERA_IFTS.search(texto_nombre) and not a["fila"]):
                texto_nombre = ""
            a["partes"] = [texto_nombre] if texto_nombre else []
        filas_de_pagina = [a for a in analizadas if a["fila"]]
        for f in filas_de_pagina:
            f["nombre_partes"] = []
        bloques: list[list[dict[str, Any]]] = [[]]
        for a in analizadas:
            if a["i"] <= cabecera:
                continue
            if a["vacia"]:
                bloques.append([])
            else:
                bloques[-1].append(a)
        for bloque in bloques:
            propias = [a for a in bloque if a["fila"]]
            primera_de_la_pagina = propias and propias[0] is (filas_de_pagina[0] if filas_de_pagina else None)
            if enteras and (len(propias) > 1 or primera_de_la_pagina and de_la_pagina_anterior):
                # Between two rows, the lines split where the row above's
                # name ends a whole cell and the one below's starts one.
                sueltas: list[dict[str, Any]] = []
                for a in bloque:
                    if not a["fila"]:
                        if a["partes"]:
                            sueltas.append(a)
                        continue
                    anterior = next((f for f in reversed(propias) if f["i"] < a["i"]), None)
                    if anterior is None and primera_de_la_pagina:
                        anterior = de_la_pagina_anterior
                    propia = [(a["i"], a["partes"][0])] if a["partes"] else []
                    if anterior is None:
                        a["nombre_partes"] += [(x["i"], x["partes"][0]) for x in sueltas] + propia
                    else:
                        cortes = []
                        for k in range(len(sueltas) + 1):
                            arriba = [p for _, p in sorted(anterior["nombre_partes"] + [
                                (x["i"], x["partes"][0]) for x in sueltas[:k]])]
                            abajo = [x["partes"][0] for x in sueltas[k:]] + [p for _, p in propia]
                            if _nombre_de_celda(arriba, enteras) and (
                                    not abajo or _clave_de_celda(" ".join(abajo).replace(_RECORTABLE, ""))
                                    in comienzos_de_celdas):
                                cortes.append(k)
                        if len(cortes) > 1:
                            # Both ways give cells: the lines go to the
                            # nearer row, if that is one of them.
                            cerca = sum(1 for x in sueltas if x["i"] - anterior["i"] < a["i"] - x["i"]) \
                                if anterior in filas_de_pagina else 0
                            parejas = any(x["i"] - anterior["i"] == a["i"] - x["i"] for x in sueltas)
                            cortes = [cerca] if cerca in cortes and not parejas else []
                        if len(cortes) != 1:
                            return []
                        anterior["nombre_partes"] += [(x["i"], x["partes"][0]) for x in sueltas[:cortes[0]]]
                        a["nombre_partes"] += [(x["i"], x["partes"][0]) for x in sueltas[cortes[0]:]] + propia
                    sueltas = []
                propias[-1]["nombre_partes"] += [(x["i"], x["partes"][0]) for x in sueltas]
                continue
            for a in bloque:
                if not a["partes"]:
                    continue
                if a["fila"]:
                    a["nombre_partes"].append((a["i"], a["partes"][0]))
                    continue
                if len(propias) == 1:
                    destino = propias[0]
                else:
                    candidatas = propias or filas_de_pagina
                    distancias = sorted((abs(f["i"] - a["i"]), f["i"]) for f in candidatas)
                    if len(distancias) > 1 and distancias[0][0] == distancias[1][0]:
                        dudosas.append((a["i"], a["partes"][0], [f for f in candidatas
                                                                 if f["i"] in (distancias[0][1], distancias[1][1])]))
                        continue
                    destino = next(f for f in candidatas if f["i"] == distancias[0][1])
                destino["nombre_partes"].append((a["i"], a["partes"][0]))
        filas += filas_de_pagina
    if len(filas) < minimo or sum(f["horas"] for f in filas) != total_declarado:
        return []
    if dudosas:
        if not enteras or len(dudosas) > 12:
            return []

        def nombre_de(fila: dict[str, Any], extra: list[tuple[int, str]]) -> str:
            return _nombre_de_celda([p for _, p in sorted(fila["nombre_partes"] + extra)], enteras) or "-"

        maneras = []
        for eleccion in range(2 ** len(dudosas)):
            extra: dict[int, list[tuple[int, str]]] = {}
            for k, (i, parte, (arriba, abajo)) in enumerate(dudosas):
                extra.setdefault(id(abajo if eleccion >> k & 1 else arriba), []).append((i, parte))
            tocadas = {id(f): f for _, _, par in dudosas for f in par}
            if all(nombre_de(f, extra.get(k, [])) != "-" for k, f in tocadas.items()):
                maneras.append(extra)
        if len(maneras) != 1:
            return []
        for f in filas:
            f["nombre_partes"] += maneras[0].get(id(f), [])
    anios = []
    for f in filas:
        codigo = next((c for _, c in f["codigos"] if re.match(r"\d[.,]\d[.,]\d", c)), None)
        anios.append(int(codigo[0]) if codigo else None)
    if None in anios:
        anios = [None] * len(filas)
    materias: list[tuple[str, int | None]] = []
    for f, anio in zip(filas, anios):
        partes = [p for _, p in sorted(f["nombre_partes"])]
        nombre = (_nombre_de_celda(partes, enteras) or "") if enteras else \
            " ".join(" ".join(p.lstrip(_RECORTABLE) for p in partes).split())
        nombre = re.sub(r"(?:\s*\(\*+\))+$", "", nombre)
        if len(nombre) < 4 or not nombre[0].isupper() or _SIN_TERMINAR_IFTS.search(nombre):
            return []
        if comparison_key(nombre) not in {comparison_key(n) for n, _ in materias}:
            materias.append((nombre, anio))
    return materias


_NUMERO_UB = re.compile(r"(?<!\S)(\d{1,2})\.\s*(?=[A-ZÁÉÍÓÚÑ¿])")
_ETIQUETA_UB = re.compile(r"^(?:\d\s*(?:[º°]|er|do|ro|to)?(?:\s*a[ñn]o)?|cuatrimestre)$", re.I)
_SIGUE_UB = re.compile(r"(?i)(?:\b(?:de|del|y|e|o|u|el|la|las|los|en|a|al|para|por|con|sobre)|,)$")


def plan_numerado_ub(texto_con_columnas: str) -> list[tuple[str, int | None]]:
    """Belgrano's distance careers' plans: the subjects numbered from 1
    ("1. Organización del turismo"), in a table by year and term or in two
    columns headed "PRIMER AÑO" and "SEGUNDO AÑO" (each column its year). A
    name too long for its cell goes on in the very next line, under its
    number ("11. Régimen Económico y Financiero del Comercio" / "Internacional").
    A note in brackets ("(correlativa con 10)") is not part of a name. Taken
    only when the numbers run from 1 without a gap; a list numbered again
    after them (the subjects' contents) is not the plan."""
    lineas = texto_con_columnas.replace("\u200b", "").splitlines()
    # The plan's table starts at its heading: a list before it (the career's
    # field of work) is not the plan.
    inicio = next((i for i, l in enumerate(lineas)
                   if re.search(r"(?i)\bASIGNATURAS?\s*$|PLAN DE ESTUDIOS\s*[–-]", l)), None)
    if inicio is None:
        return []
    lineas = lineas[inicio:]
    columnas: list[tuple[int, int]] = []
    for linea in lineas:
        anios = [(m.start(), ("primer", "segundo", "tercer", "cuarto").index(m.group(1).lower()) + 1)
                 for m in re.finditer(r"(?i)\b(PRIMER|SEGUNDO|TERCER|CUARTO)\s+A[ÑN]O\b", linea)]
        if len(anios) >= 2:
            columnas = anios
            break
    items: dict[int, dict[str, Any]] = {}
    # The column of each number whose name may still go on, and the line it was last on.
    abiertos: dict[int, tuple[int, int]] = {}
    for indice, linea in enumerate(lineas):
        numeros = list(_NUMERO_UB.finditer(linea))
        if numeros and items and (int(numeros[0].group(1)) == 1 or any(int(n.group(1)) in items for n in numeros)):
            break
        for i, numero in enumerate(numeros):
            fin = numeros[i + 1].start() if i + 1 < len(numeros) else len(linea)
            columna = numero.start()
            clave = int(numero.group(1))
            anio = min(columnas, key=lambda c: abs(c[0] - columna))[1] if columnas else None
            items[clave] = {"texto": " ".join(linea[numero.end():fin].split()), "anio": anio}
            abiertos[columna] = (clave, indice)
        if numeros or not items:
            continue
        for celda in re.finditer(r"\S+(?: \S+)*", linea):
            if _ETIQUETA_UB.match(celda.group()):
                continue
            columna = next((c for c in abiertos if abs(c - celda.start()) <= 1), None)
            if columna is None or abiertos[columna][1] != indice - 1:
                continue
            clave = abiertos[columna][0]
            items[clave]["texto"] += " " + celda.group()
            abiertos[columna] = (clave, indice)
    if len(items) < 8 or sorted(items) != list(range(1, len(items) + 1)):
        return []
    materias: list[tuple[str, int | None]] = []
    for clave in sorted(items):
        nombre = " ".join(re.sub(r"\s*\([^)]*\)", "", items[clave]["texto"]).split()).strip(" -–")
        if not nombre or _SIGUE_UB.search(nombre):
            return []
        # (``_agregar`` cleans the name and keeps a subject with its year;
        # a plan by term and year in a table gives none.)
        limpia: list[tuple[str, int]] = []
        _agregar(limpia, nombre, items[clave]["anio"] or 1)
        materias += [(n, items[clave]["anio"]) for n, _ in limpia
                     if n not in {m for m, _ in materias}]
    return materias


# Its length after the name: (C) a term, (A) a year, (B) two months.
_CODIGO_UNMA = re.compile(r"\(c[óo]d\.\s*(\d{1,3})\)\s*((?:(?!\(c[óo]d\.).)+?)\s*\((?:C|A|B)\)", re.S)


def plan_unma(ruta: str) -> list[tuple[str, int]]:
    """UNMa's plan maps (doc/mapas/*_PLAN_ESTUDIOS.pdf): a column per year
    under "1° AÑO" … "5° AÑO", and in it a box per subject, "(cód. 7) Historia
    Argentina II (C)", its name wrapped over lines and "Corr.: 04" under it.
    ``-raw`` gives each box's text whole; the year is the column its code
    sits in, between the midpoints of the year headings. Nothing unless the
    codes run from 1 without a gap and their years never go back (the
    language levels, without a code, are not read)."""
    import subprocess

    import pdfplumber

    texto = subprocess.run(["pdftotext", "-raw", ruta, "-"], capture_output=True, text=True,
                           timeout=60).stdout
    nombres: dict[int, str] = {}
    for codigo, nombre in _CODIGO_UNMA.findall(texto):
        nombre = re.sub(r"\s*Corr\.?:.*$", "", re.sub(r"\s+", " ", nombre)).strip()
        nombres.setdefault(int(codigo), nombre)
    anios: dict[int, int] = {}
    with pdfplumber.open(ruta) as pdf:
        for pagina in pdf.pages:
            palabras = pagina.extract_words()
            cabezas = sorted(((p["x0"] + p["x1"]) / 2, int(m.group(1))) for i, p in enumerate(palabras[:-1])
                             if (m := re.fullmatch(r"(\d)°", p["text"])) and palabras[i + 1]["text"] == "AÑO")
            if not cabezas:
                continue
            cortes = [(a[0] + b[0]) / 2 for a, b in zip(cabezas, cabezas[1:])]
            for i, p in enumerate(palabras[:-1]):
                if re.fullmatch(r"\(c[óo]d\.", p["text"]) and (m := re.fullmatch(r"(\d{1,3})\)", palabras[i + 1]["text"])):
                    x = p["x0"]
                    anios.setdefault(int(m.group(1)), cabezas[sum(1 for c in cortes if x > c)][1])
    if not nombres or set(nombres) != set(range(1, max(nombres) + 1)) or set(anios) != set(nombres):
        return []
    orden = [anios[c] for c in sorted(nombres)]
    if orden != sorted(orden):
        return []
    materias: list[tuple[str, int]] = []
    for codigo in sorted(nombres):
        _agregar(materias, nombres[codigo], anios[codigo])
    return materias
plan_unma.ruta = True  # type: ignore[attr-defined]


_PANEL_FAVALORO = {"primero": 1, "segundo": 2, "tercero": 3, "cuarto": 4, "quinto": 5, "sexto": 6}


def plan_favaloro(html: str) -> list[tuple[str, int]]:
    """Favaloro's plan pages ("<career>-plan-de-estudio/"): a tab per year,
    its panel's id the ordinal ("primero" … "sexto"), and in it an accordion
    of the year's subjects, each an h2 over its hours and teacher. A panel
    left empty (the template's six years over a four-year plan) gives
    nothing."""
    materias: list[tuple[str, int]] = []
    for panel in BeautifulSoup(html or "", "html.parser").select("div.vc_tta-panel[id]"):
        anio = _PANEL_FAVALORO.get(panel["id"])
        if not anio:
            continue
        for titulo in panel.select("li > h2"):
            # (Kinesiología's first year opens with its admission course.)
            if re.fullmatch(r"(?i)curso de ingreso", titulo.get_text(" ", strip=True)):
                continue
            _agregar(materias, titulo.get_text(" ", strip=True), anio)
    return materias


_ORDINAL_DEL_ANIO = {"primer": 1, "primero": 1, "segundo": 2, "tercer": 3, "tercero": 3, "cuarto": 4,
                     "quinto": 5, "sexto": 6}


def plan_totales_por_anio(texto_con_columnas: str) -> list[tuple[str, int]]:
    """A table closed year by year by its totals (the Hospital Italiano's
    Psicología and Ingeniería Biomédica, ``-layout``): a row per subject, its
    name and then its hours ("Electrotecnia   48  48  96"), the year and
    term in columns to its left on some rows only ("1°", "Anual"), and after
    a year's rows "Totales (de) primer año  528 ...". A row belongs to the
    year whose totals come next; rows after the last totals belong to no
    year and are left out, and so is a plan with a year's totals missing."""
    materias: list[tuple[str, int]] = []
    pendientes: list[str] = []
    vistos: list[int] = []
    for linea in texto_con_columnas.splitlines():
        cierre = re.search(r"(?i)\btotales?\s+(?:de(?:l)?\s+)?(\w+)\s+a[ñn]o\b", linea)
        if cierre:
            anio = _ORDINAL_DEL_ANIO.get(comparison_key(cierre.group(1)))
            if not anio:
                return []
            vistos.append(anio)
            for nombre in pendientes:
                _agregar(materias, nombre, anio)
            pendientes.clear()
            continue
        fila = re.match(r"^\s*(?:(?:\d\s*[°º]|anual)\s+)*(.*?[^\W\d_].*?)\s{2,}(\d{1,4})(?:\s+\d{1,4}){0,3}\s*$",
                        linea, re.I)
        if fila and not re.search(r"(?i)^(?:a[ñn]o|cuatrimestre|totales?|total general|carga)\b", fila.group(1)):
            pendientes.append(fila.group(1))
    if not vistos or vistos != list(range(1, len(vistos) + 1)):
        return []
    return materias


def plan_uhiba_todos(texto_con_columnas: str) -> list[tuple[str, int]]:
    """The Hospital Italiano's plans in either layout: by year headings
    (``plan_uhiba``) or in a table closed by each year's totals (its 2027
    sheets: Psicología, Ingeniería Biomédica)."""
    return plan_uhiba(texto_con_columnas) or plan_totales_por_anio(texto_con_columnas)


def plan_cemic(ruta: str) -> list[tuple[str, int]]:
    """CEMIC's plan sheets ("Plan de estudios_<Carrera>.pdf"): under each
    "1° AÑO" heading a table "Cod. | Asignatura | Cursada | Horas", two years
    side by side on a page; a row per subject, its two-digit code at the
    left and its name between the "Asignatura" and "Cursada" columns, wrapped
    onto the lines below until the next code. Nothing unless the codes run
    from 1 without a gap and their years never go back."""
    import pdfplumber

    filas: dict[int, tuple[str, int]] = {}
    with pdfplumber.open(ruta) as pdf:
        for pagina in pdf.pages:
            palabras = pagina.extract_words(keep_blank_chars=False)
            cods = [p for p in palabras if p["text"] == "Cod."]
            tablas = []
            for i, p in enumerate(palabras[:-1]):
                m = re.fullmatch(r"(\d)\s*[°º]", p["text"])
                if not m or palabras[i + 1]["text"] != "AÑO":
                    continue
                cod = next((c for c in cods if 0 < c["top"] - p["top"] < 40 and abs(c["x0"] - p["x0"]) < 40), None)
                if not cod:
                    continue
                cabecera = [q for q in palabras if abs(q["top"] - cod["top"]) < 3 and q["x0"] >= cod["x0"]]
                # (Nutrición's last table: "Cod. | Actividades obligatorias | Cursada".)
                asignatura = next((q for q in cabecera if q["text"] in ("Asignatura", "Actividades")), None)
                cursada = next((q for q in cabecera if q["text"] == "Cursada"), None)
                if asignatura and cursada:
                    tablas.append((int(m.group(1)), cod, asignatura["x0"], cursada["x0"]))
            for anio, cod, izquierda, derecha in tablas:
                # The table ends at its totals, at the year's footer ("1° AÑO",
                # "Carga horaria total") or at the page's ("Duración de la carrera").
                fin = min([q["top"] for q in palabras if q["top"] > cod["top"] + 15
                           and cod["x0"] - 10 <= q["x0"] < derecha + 150
                           and re.match(r"(?i)carga|total|duraci[óo]n|\d\s*[°º]$|año$", q["text"])] + [pagina.height])
                codigos = sorted((q for q in palabras if re.fullmatch(r"\d{1,2}", q["text"])
                                  and abs(q["x1"] - cod["x1"]) < 25 and cod["top"] < q["top"] < fin),
                                 key=lambda q: q["top"])
                for k, codigo in enumerate(codigos):
                    hasta = codigos[k + 1]["top"] - 2 if k + 1 < len(codigos) else fin
                    nombre = [q for q in palabras if izquierda - 4 <= q["x0"] < derecha - 4
                              and codigo["top"] - 3 <= q["top"] < hasta]
                    nombre.sort(key=lambda q: (round(q["top"]), q["x0"]))
                    filas.setdefault(int(codigo["text"]), (" ".join(q["text"] for q in nombre), anio))
    if not filas or set(filas) != set(range(1, max(filas) + 1)):
        return []
    # A table not read at the end leaves no gap: the sheet's last code says.
    import subprocess

    texto = subprocess.run(["pdftotext", "-layout", ruta, "-"], capture_output=True, text=True, timeout=60).stdout
    if max(filas) != max([int(c) for c in re.findall(r"(?m)^\s{2,}(\d{1,2})\s{2,}[^\W\d_]", texto)] + [0]):
        return []
    orden = [filas[c][1] for c in sorted(filas)]
    if orden != sorted(orden):
        return []
    materias: list[tuple[str, int]] = []
    for codigo in sorted(filas):
        _agregar(materias, *filas[codigo])
    return materias
plan_cemic.ruta = True  # type: ignore[attr-defined]


def plan_iuse(texto_con_columnas: str) -> list[tuple[str, int]]:
    """IUSE's plan sheets (``-layout``): under "Primer año" … headings
    (beside the term), a numbered row per subject, "12  Inglés II  3  48
    Cuatrimestral  Presencial". Nothing unless the numbers run from 1
    without a gap."""
    filas: dict[int, tuple[str, int]] = {}
    anio = None
    for linea in texto_con_columnas.splitlines():
        cabeza = re.match(r"^\s*(primer|segundo|tercer|cuarto|quinto|sexto)o?\s+a[ñn]o\b", linea, re.I)
        if cabeza:
            anio = _ORDINAL_DEL_ANIO[cabeza.group(1).lower()]
            continue
        fila = re.match(r"^\s*(\d{1,2})\s{2,}(\S.*?)\s{2,}\d", linea)
        if fila and anio:
            filas.setdefault(int(fila.group(1)), (fila.group(2), anio))
    if not filas or set(filas) != set(range(1, max(filas) + 1)):
        return []
    materias: list[tuple[str, int]] = []
    for numero in sorted(filas):
        _agregar(materias, *filas[numero])
    return materias


_ANIO_EN_FOLLETO = re.compile(r"(?i)^(?:(\d)\s*[º°]?|(primer|segundo|tercer|cuarto|quinto|sexto)o?)$")
_ETIQUETA_DE_FOLLETO = re.compile(
    r"(?i)^(?:(?:primer|segundo|tercer|cuarto)o?\s+(?:quarter|cuatrimestre|semestre|trimestre)|"
    r"\d\s*[º°]?\s*(?:quarter|cuatrimestre|semestre|trimestre)|anual(?:es)?|cuatrimestral(?:es)?|"
    r"\(.*\)|[-–•·]\s.*)$")
_FIN_DE_FOLLETO = re.compile(
    r"(?i)^(?:referencias|m[óo]dulo optativo|formaci[óo]n\b|los estudiantes|carrera:|t[íi]tulo:|"
    r"universidad austral|alcance|perfil|salida laboral|campo laboral|requisitos|contacto|[áa]reas$|"
    r"otr[oa]s (?:actividades|requisitos)|diplomatura de orientaci|doble titulaci)")
_CORTADO_EN = re.compile(r"(?i)\s(?:y|e|o|u|de|del|la|las|el|los|en|con|para|a|al|no)$")
_CONTINUA = re.compile(r"^(?:[a-záéíóúñ]|(?:y|e|o|u|de|del|la|las|el|los|en|con|para|a)\s)")


def plan_folleto_columnas(ruta: str) -> list[tuple[str, int]]:
    """A brochure's plan laid out in columns of years (Austral's): a heading
    per year ("1º AÑO", "PRIMER AÑO") over its subjects, two or three years
    side by side and the next ones below them. A year's block runs from its
    heading down to the next heading of its column; its lines are its
    subjects, a line slightly indented past the block's margin, opening in
    lower case ("del Adulto", "y Hierbas") or following one cut after a
    connector ("Fundamentos de Enfermería y") going on the one before. Term
    labels ("PRIMER QUARTER"), bullets and what they wrap, remarks in
    brackets, tracks' subjects and words far to the right (a legend) are not
    subjects; a heading in capitals, the brochure's references or optional
    module end a block. Text set on its side is left out. Nothing unless the
    years run from the first without a gap."""
    import pdfplumber

    materias: list[tuple[str, int]] = []
    with pdfplumber.open(ruta) as pdf:
        for pagina in pdf.pages:
            # (Text set on its side down a margin is not the plan's.)
            palabras = [p for p in pagina.extract_words(keep_blank_chars=False, use_text_flow=False)
                        if p.get("upright", True)]
            cabezas = []
            for i, p in enumerate(palabras[:-1]):
                siguiente = palabras[i + 1]
                m = _ANIO_EN_FOLLETO.match(p["text"])
                if m and siguiente["text"].upper() == "AÑO" and abs(siguiente["top"] - p["top"]) < 3:
                    anio = int(m.group(1)) if m.group(1) else _ORDINAL_DEL_ANIO[m.group(2).lower()]
                    cabezas.append({"anio": anio, "x0": p["x0"], "top": p["top"],
                                    "bottom": max(p["bottom"], siguiente["bottom"])})
            if not cabezas:
                continue
            columnas = sorted({round(c["x0"] / 40) for c in cabezas})
            xs = sorted({min(c["x0"] for c in cabezas if round(c["x0"] / 40) == k) for k in columnas})
            ancho = min((b - a for a, b in zip(xs, xs[1:])), default=pagina.width - xs[0])
            for cabeza in cabezas:
                izquierda = cabeza["x0"] - 12
                derecha = min([x - 12 for x in xs if x > cabeza["x0"] + 40] + [cabeza["x0"] + ancho - 12])
                abajo = min([c["top"] for c in cabezas if c["top"] > cabeza["top"] + 5 and abs(c["x0"] - cabeza["x0"]) < 40]
                            + [pagina.height])
                suyas = [p for p in palabras if izquierda <= p["x0"] < derecha and cabeza["bottom"] + 1 < p["top"] < abajo - 1]
                lineas: list[list[dict]] = []
                for p in sorted(suyas, key=lambda p: (p["top"], p["x0"])):
                    if lineas and abs(lineas[-1][0]["top"] - p["top"]) < 3:
                        lineas[-1].append(p)
                    else:
                        lineas.append([p])
                # A name the cell wrapped sits closer under its first line
                # than the next subject does: Psicología's "Metodología de la
                # Investigación" / "Cuantitativa" 8 points apart, subjects 10.
                saltos = [b[0]["top"] - a[0]["top"] for a, b in zip(lineas, lineas[1:])]
                paso = sorted(saltos)[len(saltos) // 2] if len(saltos) >= 4 else None
                items: list[list] = []
                margen = None
                tras_vineta = False
                anterior = None
                for linea in lineas:
                    pegada = bool(paso and anterior is not None and linea[0]["top"] - anterior < 0.85 * paso)
                    anterior = linea[0]["top"]
                    # A wide gap leaves the name: what follows is a legend beside it ("Cursada").
                    linea = sorted(linea, key=lambda p: p["x0"])
                    corte = next((k for k in range(1, len(linea)) if linea[k]["x0"] - linea[k - 1]["x1"] > 40), len(linea))
                    linea = linea[:corte]
                    texto = clean_text(" ".join(p["text"] for p in linea))
                    if not texto or _ETIQUETA_DE_FOLLETO.match(texto):
                        # (What a bullet wraps onto the next line is the bullet's.)
                        tras_vineta = bool(texto) and texto[0] in "-–•·"
                        continue
                    # "Optativa" alone is a choice's place, not a subject; a
                    # remark below it ("y adaptarse según...") is not its name.
                    if re.match(r"(?i)^optativas?(?:\s+(?:[IVX]+|\d+))?$", texto):
                        tras_vineta = True
                        continue
                    letras = [c for c in texto if c.isalpha()]
                    # A heading in capitals ("DOBLE TITULACIÓN ...") or the brochure's own matter ends the year.
                    if _FIN_DE_FOLLETO.match(texto) or (len(letras) >= 8 and sum(c.isupper() for c in letras) > 0.6 * len(letras)):
                        break
                    # A track's own subject ("Track BT: Análisis Genómico") is one choice, not the plan's.
                    if re.match(r"(?i)track\b", texto):
                        continue
                    x = min(p["x0"] for p in linea)
                    # (A slight indent goes on; a word far to the right is beside the list, not in it.)
                    if margen is not None and x > margen + 40:
                        continue
                    sigue = _CONTINUA.match(texto) or (margen is not None and x > margen + 4)
                    if tras_vineta and (sigue or pegada):
                        continue
                    tras_vineta = False
                    if items and (sigue or pegada or _CORTADO_EN.search(items[-1][0])):
                        items[-1][0] += " " + texto
                        continue
                    margen = x if margen is None else min(margen, x)
                    items.append([texto, cabeza["anio"]])
                for nombre, anio in items:
                    _agregar(materias, nombre, anio)
    anios = sorted({a for _, a in materias})
    if not anios or anios != list(range(1, max(anios) + 1)):
        return []
    return materias
plan_folleto_columnas.ruta = True  # type: ignore[attr-defined]


_CUATRIMESTRE_UNTREF = re.compile(r"(?i)^(primer|segundo|tercer|cuarto|quinto|sexto|s[ée]ptimo|octavo|noveno|d[ée]cimo)o?\s+cuatrimestre$")
_NUMERO_DEL_CUATRIMESTRE = {"primer": 1, "segundo": 2, "tercer": 3, "cuarto": 4, "quinto": 5, "sexto": 6,
                            "septimo": 7, "séptimo": 7, "octavo": 8, "noveno": 9, "decimo": 10, "décimo": 10}


def plan_untref(html: str) -> list[tuple[str, int]]:
    """UNTREF's career pages (untref.edu.ar/carrera/...): under the block
    titled "Plan de estudios", a heading per year ("Primer Año") or per term
    ("PRIMER CUATRIMESTRE", whose year is half its number, rounded up) over
    its subjects, a list or paragraphs opened by a dash. The notes that
    follow ("(*) Asignaturas optativas") or another bold heading once the
    subjects began ("Temáticas ofrecidas para el seminario optativo") end
    it; an optional subject ("(optativa)") is a choice, and the alternative
    formative paths (TFA) are activities, not subjects. A block with no
    dash nor list (Instrumentación Quirúrgica's) has a paragraph per
    subject under each term, up to "OTROS REQUERIMIENTOS"."""
    soup = BeautifulSoup(html or "", "html.parser")
    bloque = next((g for g in soup.select("div.carreras-grid")
                   if re.match(r"(?i)plan de estudios?$", _texto(g.select_one(".carreras-tit")) or "")), None)
    contenido = bloque.select_one(".content-block") if bloque else None
    materias: list[tuple[str, int]] = []
    anio = None

    def agregar(nombre: str) -> None:
        nombre = re.sub(r"^[•\-–]\s*", "", nombre)
        if not anio or re.match(r"(?i)trayectos? formativos? alternativos?", nombre) or re.search(r"(?i)\(optativa\)", nombre):
            return
        _agregar(materias, re.sub(r"\s*\(\*+\)\s*$", "", nombre), anio)

    elementos = contenido.find_all(["p", "div", "ul"], recursive=False) if contenido else []
    sin_guiones = not any(e.name == "ul" or re.match(r"^[-–•]\s", _texto(e) or "") for e in elementos)
    for elemento in elementos:
        texto = _texto(elemento)
        if elemento.name == "ul":
            for item in elemento.find_all("li"):
                agregar(_texto(item))
            continue
        if not texto:
            continue
        if texto.startswith("("):
            break
        cuatrimestre = _CUATRIMESTRE_UNTREF.match(texto)
        if cuatrimestre:
            anio = (_NUMERO_DEL_CUATRIMESTRE[cuatrimestre.group(1).lower()] + 1) // 2
            continue
        if anio_de(texto):
            anio = anio_de(texto)
            continue
        if re.match(r"^[-–•]\s", texto):
            agregar(texto)
            continue
        if re.match(r"(?i)otros requ(?:isitos|erimientos)\b", texto):
            break
        # (A plain paragraph is a subject only in a block of plain paragraphs,
        # and not a bold heading nor a sentence.)
        if sin_guiones and anio and not elemento.find(["b", "strong"]) and len(texto) < 120 \
                and not texto.endswith("."):
            agregar(texto)
            continue
        if materias:
            break
    return materias


_PALABRA_CON_CAJA = re.compile(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">([^<]+)</word>')
_FIN_DEL_ANEXO_UNTREF = re.compile(r"(?i)^(?:otros requisitos|observaciones)\b")


def plan_untref_anexo(cajas: str) -> list[tuple[str, int]]:
    """UNTREF's plans as the Ministry's annex prints them (``-bbox-layout``):
    a table "COD  ASIGNATURA  REGIMEN ..." under "PRIMER CUATRIMESTRE" ...
    headings, each row's name centred on its row and wrapped over as many
    lines as it needs, above and below the line of its code and its
    "Cuatrimestral" ("Introducción a la" / "592 Problemática del Mundo" /
    "Contemporáneo"). Nearness cannot tell whose a line is ("Introducción a
    la" sits as near the row above), so each row takes, in order, the next
    lines whose middle is the row's own; the last row of a page may end on
    its own line, its cell going on over the page, and a page's first rows
    are of the term the page before ended in. The lines under a page's last
    row, one below the other, start the name of the next page's first row
    ("Seminario de Investigación" / "167 Integrada", Geografía's
    complementation). Any other line no row takes gives nothing. "OTROS REQUISITOS" (the languages, of no term) ends it;
    choices and the formative paths (TFA) are not subjects."""
    materias: list[tuple[str, int]] = []
    # (A term goes on over the page, and so may a name.)
    anterior = None
    arrastre: list[tuple[float, str]] = []
    for contenido in re.findall(r"<page\b.*?</page>", cajas or "", re.S):
        palabras = [(float(x0), float(y0), float(x1), float(y1), clean_text(unescape(t)))
                    for x0, y0, x1, y1, t in _PALABRA_CON_CAJA.findall(contenido)]
        cabeza, techo = next(((x0, y1) for x0, _, _, y1, t in palabras if t == "ASIGNATURA"), (None, None))
        regimenes = [(x0, (y0 + y1) / 2) for x0, y0, _, y1, t in palabras if t in ("Cuatrimestral", "Anual")]
        if cabeza is None or not regimenes:
            continue
        regimen = min(x for x, _ in regimenes)
        lineas: dict[float, list[tuple[float, str]]] = {}
        enteras: dict[float, list[tuple[float, str]]] = {}
        for x0, y0, x1, y1, t in palabras:
            enteras.setdefault(round((y0 + y1) / 2, 1), []).append((x0, t))
            # The name's column: left of the term, and not the code ("217/25" / "9").
            if x1 <= regimen + 1 and not (x0 < cabeza - 10 and re.fullmatch(r"[\d/]+", t)):
                lineas.setdefault(round((y0 + y1) / 2, 1), []).append((x0, t))
        # A term's heading may run past the names' column (a table without
        # codes, Resolución de Conflictos'): it is read on its whole line.
        for y, l in enteras.items():
            if y in lineas and _CUATRIMESTRE_UNTREF.match(" ".join(t for _, t in sorted(l))):
                lineas[y] = l
        textos = sorted((y, " ".join(t for _, t in sorted(l))) for y, l in lineas.items())
        fin = next((y for y, t in textos if _FIN_DEL_ANEXO_UNTREF.match(t)), math.inf)
        filas = sorted(y for _, y in regimenes if y < fin)
        if not filas:
            return [] if arrastre else materias
        titulos, nombres = [], []
        for y, texto in textos:
            cuatrimestre = _CUATRIMESTRE_UNTREF.match(texto)
            if cuatrimestre:
                titulos.append((y, (_NUMERO_DEL_CUATRIMESTRE[cuatrimestre.group(1).lower()] + 1) // 2))
            # (The header above the first row -- near it on a page that goes on
            # with the term before, UNAHUR's -- and the degree a part leads to.)
            elif max(filas[0] - 30, techo) < y < fin and not re.match(r"(?i)t[íi]tulos?:|carga horaria", texto):
                nombres.append((y, texto))
        for fila in filas:
            anio = next((a for y, a in reversed(titulos) if y < fila), anterior)
            if anio is None:
                return []
            # Lines one below the other, from the first not taken.
            seguidas = 1
            while seguidas < len(nombres) and 10 < nombres[seguidas][0] - nombres[seguidas - 1][0] < 13:
                seguidas += 1
            n = next((n for n in range(1, seguidas + 1)
                      if abs(sum(y for y, _ in nombres[:n]) / n - fila) < 1.5), None) if nombres else None
            if n is None and nombres and fila == filas[-1]:
                n = next((n for n in range(1, seguidas + 1) if abs(nombres[n - 1][0] - fila) < 1.5), None)
            if n is None:
                return []
            tomadas = arrastre + nombres[:n]
            arrastre = []
            del nombres[:n]
            nombre = " ".join(t for _, t in tomadas)
            if not re.match(r"(?i)trayectos? formativos? alternativos?|seminario electivo", nombre):
                _agregar(materias, nombre, anio)
        if nombres and fin == math.inf and nombres[0][0] > filas[-1] + 1.5 \
                and all(10 < b[0] - a[0] < 13 for a, b in zip(nombres, nombres[1:])):
            arrastre, nombres = nombres, []
        if nombres:
            return []
        if fin < math.inf:
            break
        anterior = titulos[-1][1] if titulos else anterior
    return [] if arrastre else materias


plan_untref_anexo.cajas = True  # type: ignore[attr-defined]


_FILA_FCV = re.compile(r"^(?P<antes>.*?)\s{2,}(?:Obligatoria|Optativa)\s+(?:Cuatrimestral|Anual|Bimestral)\s+\d+\s*horas")


def plan_fcv_unlp(texto_con_columnas: str) -> list[tuple[str, int]]:
    """UNLP Veterinarias' plan sheet (``-layout``): under "PRIMER AÑO" …
    headings, a row per subject, its name and then "Obligatoria
    Cuatrimestral 70 horas", the term ("Primer" / "cuatrimestre") in the
    left margin. A name the cell wrapped sits on lines of its own above and
    below a row with none ("Infectología, zoonosis y enfermedades exóticas
    y" / "emergentes"): they are that row's. A yearly subject printed in
    both terms is one; "Microbiología l" is its roman "I"."""
    margen = re.compile(r"(?i)^\s*(?:primer|segundo)?\s*(?:cuatrimestre)?\s*$")
    materias: list[tuple[str, int]] = []
    anio = None
    filas: list[list] = []
    suelta: list[str] = []
    for linea in texto_con_columnas.splitlines():
        cabeza = re.match(r"(?i)^\s*(primer|segundo|tercer|cuarto|quinto|sexto)o?\s+a[ñn]o\s*$", linea)
        if cabeza:
            anio, suelta = _ORDINAL_DEL_ANIO[cabeza.group(1).lower()], []
            continue
        if not anio:
            continue
        fila = _FILA_FCV.match(linea)
        if fila:
            nombre = re.sub(r"(?i)^\s*(?:primer|segundo)?\s*(?:cuatrimestre)?\s{2,}", "", fila.group("antes")).strip()
            filas.append([" ".join(suelta + [nombre]).strip(), anio, not nombre])
            suelta = []
            continue
        texto = re.sub(r"(?i)^\s*(?:primer|segundo|cuatrimestre)\s{2,}", "", linea).strip()
        if not texto or margen.match(linea) or re.match(r"(?i)asignatura|carga horaria|plan de estudios|[….]{5,}|\d{4} \d{3}", texto):
            continue
        # A line below a row the name left empty ends that name; one above a row starts the next.
        if filas and filas[-1][2] and filas[-1][1] == anio and not suelta:
            filas[-1][0] += " " + texto
            filas[-1][2] = False
        else:
            suelta.append(texto)
    for nombre, anio, _ in filas:
        _agregar(materias, re.sub(r"\bll\b", "II", re.sub(r"\s+l$", " I", nombre)), anio)
    return materias


_FILA_UNAHUR_TABLA = re.compile(r"^\s*(\d)\s+[A-Z]{2,4}\s+(\d{1,2})\s+(?:(\S.*?)\s{2,})?[CAB]\s+\d")
# (Nutrición's: no year column, the year a heading "1° Año" over the rows.)
# (A row may end at its length, its hours on the next line: Nutrición's 28.)
_FILA_UNAHUR_SIN_ANIO = re.compile(r"^\s*()(\d{1,2})\s+(?:(\S.*?)\s{2,})?[CAB](?:\s+\d|\s*$)")


def plan_unahur_tabla(texto_con_columnas: str) -> list[tuple[str, int]]:
    """UNAHUR's plan documents of 2025 and 2026 ("Plan de Estudios: ...",
    ``-layout``): a table "Año | Campo | Nro | ASIGNATURA | C/A | hours",
    a row per subject ("2 CFB 9 Redes de computadoras C 4 64 61 125 5").
    A name the cell wrapped is centred on its row: its lines sit above and
    below a row left without one ("Introducción a lógica y problemas" /
    "1 CFB 2 C 4 ..." / "computacionales"), or above a row that holds the
    rest. Nothing unless the numbers run
    from 1 without a gap."""
    filas: dict[int, list] = {}
    arriba: list[str] = []
    falta_abajo = None
    anio = None
    for linea in texto_con_columnas.splitlines():
        cabeza = re.match(r"^\s*(\d)\s*[°º]\s*A[ñn]o\s*$", linea)
        if cabeza:
            anio, arriba = int(cabeza.group(1)), []
            continue
        fila = _FILA_UNAHUR_TABLA.match(linea) or (anio and _FILA_UNAHUR_SIN_ANIO.match(linea))
        if fila:
            nombre = (fila.group(3) or "").strip()
            numero = int(fila.group(2))
            if numero not in filas:
                # (Or its first line above a row that holds the rest: Ciberseguridad's.)
                filas[numero] = [" ".join(arriba + ([nombre] if nombre else [])), int(fila.group(1) or anio)]
                falta_abajo = filas[numero] if not nombre else None
            arriba = []
            continue
        texto = linea.strip()
        if re.match(r"TOTAL DE LA CARRERA", texto):
            break
        # (The rest of a name beside the hours its row left for this line.)
        if falta_abajo is not None and re.match(r"^[^\W\d_][^\d]*?\s{2,}\d", texto):
            falta_abajo[0] += " " + re.split(r"\s{2,}", texto)[0]
            falta_abajo = None
            continue
        # The table's head ("Camp", "Sema"/"nal", "HS."), a total, a term or a
        # page's number ends what was gathered above. ("Regional" ends in "nal" too.)
        cabecera = re.search(r"TOTAL|ASIGNATURA|HS\.|^Añ|CUATRIMESTRE|Unidad curricular|^(?:Camp|Sema|Total|nal|o)\b.{0,12}$|^\d+$", texto)
        if not texto or cabecera or re.search(r"\d", texto):
            arriba = [] if cabecera else arriba
            continue
        if falta_abajo is not None:
            falta_abajo[0] += " " + texto
            falta_abajo = None
        else:
            arriba.append(texto)
    if not filas or set(filas) != set(range(1, max(filas) + 1)) or any(not n for n, _ in filas.values()):
        return []
    materias: list[tuple[str, int]] = []
    for numero in sorted(filas):
        _agregar(materias, *filas[numero])
    return materias


# (The code a number, "0279", or a letter, "B" (Zootecnista's); "obligatorio" too.)
_FILA_UNSADA = re.compile(r"^\s*(\d)\s+\d\s*[°º]\s+[A-Z]{1,4}\s+(?:\d{3,4}|[A-Z]{1,2})\s+(?:(\S.*?)\s+)?"
                          r"((?i:obligatori[oa]|optativ[oa]|electiv[oa]))\b")


def plan_unsada(texto_con_columnas: str) -> list[tuple[str, int]]:
    """UNSAdA's plan sheets ("Plan de estudios | <carrera>", ``-layout``):
    a table "Año | Cuatrim. | Depto. | Código | Nombre de la asignatura |
    Carácter | hours", a row per subject, a long name centred on its row (a
    line above and one below a row left without it). The sheet states how
    many compulsory subjects the plan has ("8. Cantidad de asignaturas
    obligatorias: 19"): nothing unless the compulsory rows are as many. An
    elective's slot ("Electiva NFG (*)") is not a subject."""
    declarada = re.search(r"(?i)cantidad de asignaturas obligatorias\s*\n?\s*(\d+)", texto_con_columnas)
    filas: list[list] = []
    arriba: list[str] = []
    falta_abajo = None
    abajo = 0
    for linea in texto_con_columnas.splitlines():
        fila = _FILA_UNSADA.match(linea)
        if fila:
            nombre = (fila.group(2) or "").strip()
            filas.append([" ".join(arriba + ([nombre] if nombre else [])), int(fila.group(1)), fila.group(3)])
            # A name centred on a row without it takes as many lines below as
            # above ("Enfoques" / "Pedagógicos" / row / "Aplicados a la" /
            # "Fonoaudiología"); one cut after a connector goes on one line
            # below ("Gestión de Servicios Sanitarios y").
            abajo = len(arriba) if not nombre else (1 if _CORTADO_EN.search(nombre) else 0)
            falta_abajo = filas[-1] if abajo else None
            arriba = []
            continue
        texto = linea.strip()
        if not texto or re.search(r"\d|Total|Carga horaria|Nombre de la|Carrera:|T[íi]tulo:|\(1° o 2°\)", texto):
            arriba = []
            continue
        if falta_abajo is not None:
            falta_abajo[0] += " " + texto
            abajo -= 1
            falta_abajo = falta_abajo if abajo > 0 else None
        else:
            arriba.append(texto)
    obligatorias = [f for f in filas if f[2].lower().startswith("obligatori")]
    if not declarada or len(obligatorias) != int(declarada.group(1)) or any(not n for n, _, _ in filas):
        return []
    materias: list[tuple[str, int]] = []
    for nombre, anio, caracter in obligatorias:
        if re.match(r"(?i)electiva\b", nombre):
            continue
        _agregar(materias, re.sub(r"\s*\(\*+\)\s*$", "", nombre), anio)
    return materias
plan_unsada.respaldo = True  # type: ignore[attr-defined]


_ANIO_DE_TABLA = {"primer": 1, "primero": 1, "segundo": 2, "tercer": 3, "tercero": 3, "cuarto": 4, "quinto": 5, "sexto": 6}
_PLAN_ANTERIOR = re.compile(r"(?i)transici[óo]n|plan(?: de estudios?)?\s*(?:19|20)\d\d\b|plan anterior")


def plan_tablas_por_anio(html: str) -> list[tuple[str, int]]:
    """A page whose current plan is tables headed by "Primer Año", "Segundo
    Año" … one column per year (IUA's faculties), or one table per year and
    term ("PRIMER AÑO – PRIMER CUATRIMESTRE"). Only the tables before the
    page's next heading naming a transition or an older plan are read: the
    page keeps the plans it replaced below the current one. A table with no
    year in its head, or a cell that is not a name, ends nothing: it is left
    out. Empty when the page has no such table."""
    soup = BeautifulSoup(html or "", "html.parser")
    cuerpo = soup.find("article") or soup.find("main") or soup
    # The degree's own name closes the table of some pages ("Contador Público").
    titulo = comparison_key(re.split(r"\s+[–|-]\s+", soup.title.get_text(" ", strip=True))[0]) if soup.title else ""
    materias: list[tuple[str, int]] = []
    vistas_tablas = 0
    for el in cuerpo.find_all(["h1", "h2", "h3", "h4", "table"]):
        if el.name != "table":
            if vistas_tablas and _PLAN_ANTERIOR.search(el.get_text(" ", strip=True)):
                break
            continue
        filas = el.find_all("tr")
        if not filas:
            continue
        cabecera = [c.get_text(" ", strip=True) for c in filas[0].find_all(["td", "th"])]
        anios: list[int | None] = []
        for celda in cabecera:
            m = re.match(r"(?i)\s*(\w+)\s+a[ñn]o\b", celda)
            anios.append(_ANIO_DE_TABLA.get(comparison_key(m.group(1))) if m else None)
        if not any(anios):
            continue
        vistas_tablas += 1
        for fila in filas[1:]:
            for columna, celda in enumerate(fila.find_all(["td", "th"])):
                anio = anios[columna] if columna < len(anios) else None
                nombre = re.sub(r"\s*\(\*+\)\s*$|\s*\*+\s*$", "", " ".join(celda.get_text(" ", strip=True).split()))
                if re.fullmatch(r"(?i)\d+\s*[º°o]?\s*semestre|\d+\s*[º°o]?\s*cuatrimestre", nombre):
                    continue
                if anio and nombre and re.search(r"[A-Za-zÁÉÍÓÚáéíóúñÑ]{3}", nombre) \
                        and comparison_key(nombre) != titulo:
                    _agregar(materias, nombre, anio)
    return materias


def plan_up_semestres(html: str) -> list[tuple[str, int]]:
    """Palermo's one-year postdegree plan, written as "Primer semestre" and
    "Segundo semestre" over short lists of names (Escribanía): the whole plan
    is the names under both headings, up to the line that gives the degree.
    A page that does not print both headings is not read."""
    soup = BeautifulSoup(html or "", "html.parser")
    for etiqueta in soup(["script", "style"]):
        etiqueta.decompose()
    lineas = [clean_text(t) for t in soup.get_text("\n").split("\n")]
    lineas = [t for t in lineas if t]
    # A heading may be split over two lines ("Primer" / "semestre").
    unidas: list[str] = []
    i = 0
    while i < len(lineas):
        if re.fullmatch(r"(?i)(primer|segundo)", lineas[i]) and i + 1 < len(lineas) \
                and re.fullmatch(r"(?i)semestre", lineas[i + 1]):
            unidas.append(f"{lineas[i]} semestre")
            i += 2
            continue
        unidas.append(lineas[i])
        i += 1
    materias: list[tuple[str, int]] = []
    semestres = 0
    dentro = False
    for linea in unidas:
        if re.fullmatch(r"(?i)(primer|segundo) semestre", linea):
            semestres += 1
            dentro = True
            continue
        if dentro and re.match(r"(?i)los graduados|ver m[aá]s|contenidos acad", linea):
            break
        if dentro and re.search(r"[A-Za-zÁÉÍÓÚáéíóúñÑ]{3}", linea):
            _agregar(materias, linea, 1)
    return materias if semestres == 2 else []


_CONECTOR_FINAL = re.compile(r"(?i)(?:\b(?:de|del|la|las|los|y|e|en|a|con|para|por)|[(-])$")


def plan_um_filas(texto: str) -> list[tuple[str, int]]:
    """Universidad de Mendoza's health-faculty plan sheets (``-layout``
    text): a row per subject that opens with its year ("1°", "2º"), its term,
    its code ("K12", "Od-03", "Nu05"), then its name and its hours. A name the
    cell wrapped has its pieces in the lines above and below the row, at the
    name's column: they go with the row that is missing them (an empty name,
    a connector or an open bracket at its end), the one above first. A row
    whose name stays empty makes the sheet unreadable."""
    lineas = texto.splitlines()
    fila = re.compile(r"^(\s*)(\d)\s*[°º]\s+(?:\S+\s+){0,3}?([A-Za-z]{1,3}-?\d{1,3})\s{2,}(.*)$")
    filas: list[dict] = []
    columna = None
    for i, linea in enumerate(lineas):
        m = fila.match(linea)
        if not m:
            continue
        resto = m.group(4)
        # The name is what comes before the first run of spaces that precedes the hours.
        partes = re.split(r"\s{3,}", resto.strip())
        nombre = partes[0] if partes and not re.fullmatch(r"[\d\s.,-]*", partes[0]) else ""
        if nombre:
            columna = linea.index(nombre, linea.index(m.group(3)) + len(m.group(3)))
        filas.append({"i": i, "anio": int(m.group(2)), "nombre": clean_text(nombre),
                      "cod": linea.index(m.group(3), len(m.group(1)))})
    if not filas or columna is None:
        return []
    es_fila = {f["i"] for f in filas}

    def pieza(j: int, codigo: int) -> str | None:
        if j < 0 or j >= len(lineas) or j in es_fila:
            return None
        linea = lineas[j]
        # At or past the column of the row's code, where the names are.
        if not linea.strip() or len(linea) - len(linea.lstrip()) < codigo:
            return None
        cuerpo = clean_text(linea)
        if re.search(r"\s{3,}", linea.strip()) or not re.search(r"[A-Za-zÁÉÍÓÚáéíóúñÑ]{3}", cuerpo):
            return None
        # (A rule of the plan, not a piece of a name.)
        if re.match(r"(?i)(?:para|el|la|los|las|entre|a[nñ]o|c[oó]digo)\b.{20,}", cuerpo) and len(cuerpo) > 45:
            return None
        return cuerpo

    usadas: set[int] = set()
    materias: list[tuple[str, int]] = []
    for f in filas:
        nombre = f["nombre"]
        incompleto = not nombre or _CONECTOR_FINAL.search(nombre) or nombre.count("(") > nombre.count(")")
        arriba = pieza(f["i"] - 1, f["cod"]) if f["i"] - 1 not in usadas else None
        if arriba and (not nombre or incompleto):
            nombre = clean_text(f"{arriba} {nombre}")
            usadas.add(f["i"] - 1)
            incompleto = _CONECTOR_FINAL.search(nombre) or nombre.count("(") > nombre.count(")")
        if not nombre or incompleto or f["nombre"] == "":
            abajo = pieza(f["i"] + 1, f["cod"])
            if abajo and (f["i"] + 1) not in usadas:
                nombre = clean_text(f"{nombre} {abajo}")
                usadas.add(f["i"] + 1)
        if not nombre or _CONECTOR_FINAL.search(nombre) or nombre.count("(") > nombre.count(")"):
            return []
        nombre = re.sub(r"(?i)\s*\((?:promocional|anual|cuatrimestral)\)\s*$", "", nombre)
        _agregar(materias, nombre, f["anio"])
    return desde_el_primero(materias)


def plan_um_vinetas(texto: str) -> list[tuple[str, int]]:
    """Universidad de Mendoza's tecnicatura sheets: a heading per year
    ("1.º AÑO") over two columns of bullets, the first term's and the
    second's. Every bullet is a subject of that year; a line without a
    bullet is not read."""
    materias: list[tuple[str, int]] = []
    anio = None
    for linea in texto.splitlines():
        cabecera = re.match(r"^\s*(\d)\s*\.?\s*[º°o]?\s*A[ÑN]O\b", linea)
        if cabecera:
            anio = int(cabecera.group(1))
            continue
        # The last year is headed by its stage, not by its number.
        if anio and re.match(r"^\s*PR[ÁA]CTICA FINAL SUPERVISADA\s*$", linea):
            anio += 1
            continue
        if re.match(r"^\s*INFORMACI[ÓO]N Y S[ÍI]NTESIS", linea):
            break
        if anio and "•" in linea:
            for pedazo in linea.split("•")[1:]:
                _agregar(materias, pedazo, anio)
    return desde_el_primero(materias)


def plan_umendoza_todos(texto: str) -> list[tuple[str, int]]:
    """Each of the UMendoza's plan sheets in the way it is written."""
    return plan_umendoza(texto) or plan_um_filas(texto) or plan_um_vinetas(texto)


plan_umendoza_todos.respaldo = True  # type: ignore[attr-defined]  # the general reader after these


def plan_ucu(html: str) -> list[tuple[str, int]]:
    """The UCU's career pages: under "Plan de estudios" a heading per year
    ("Primer Año") over its terms ("Primer cuatrimestre", "Segundo
    cuatrimestre"), each a run of short lines, one subject each. The lists
    under "Optativas" are the choices offered, not the plan's subjects, and
    are left out; a line of prose or a heading that is neither a year nor a
    term ends the plan."""
    soup = BeautifulSoup(html or "", "html.parser")
    for etiqueta in soup(["script", "style", "nav", "header", "footer"]):
        etiqueta.decompose()
    lineas = [clean_text(t) for t in soup.get_text("\n").split("\n")]
    lineas = [t for t in lineas if t]
    try:
        inicio = next(i for i, t in enumerate(lineas) if re.fullmatch(r"(?i)plan de estudios?", t))
    except StopIteration:
        return []
    materias: list[tuple[str, int]] = []
    anio, optativas = None, False
    for linea in lineas[inicio + 1:]:
        if re.fullmatch(r"(?i)(?:primer|segundo|tercer|cuarto|quinto|sexto)\s+a[ñn]o", linea):
            anio, optativas = anio_de(linea), False
            continue
        if re.fullmatch(r"(?i)(?:primer|segundo)\s+cuatrimestre:?", linea):
            optativas = False
            continue
        if re.fullmatch(r"(?i)(?:optativas?|opcional(?:es)?):?", linea):
            optativas = True
            continue
        if anio is None:
            continue
        # The plan ends at its next heading: a long line, or one that closes with a colon.
        if len(linea) > 90 or linea.endswith(":") or re.match(r"(?i)(?:facultad|escuela|departamento) de\b|(?:perfil|t[íi]tulo|alcances|requisitos|salida|contacto|duraci[óo]n|modalidad|sede|inscrip)", linea):
            break
        if not optativas:
            _agregar(materias, linea, anio)
    return desde_el_primero(materias)


def plan_uda(html: str) -> list[tuple[str, int]]:
    """The UDA's career pages: a heading per year ("PRIMER AÑO") over its
    terms ("PRIMER SEMESTRE", "ASIGNATURA ANUAL"), each subject a numbered
    line ("7. Estadística*"). A page that prints a plan more than once (the
    old one and "Plan de estudio 2026") is read in its last: the newest. The
    plan ends at the line of the degree ("TÍTULO DE GRADO: …"); the
    intermediate degree's line, in the middle of it, does not end it."""
    soup = BeautifulSoup(html or "", "html.parser")
    for etiqueta in soup(["script", "style", "nav", "header", "footer"]):
        etiqueta.decompose()
    lineas = [clean_text(t) for t in soup.get_text("\n").split("\n")]
    lineas = [t for t in lineas if t]
    primeros = [i for i, t in enumerate(lineas) if re.fullmatch(r"(?i)primer a[ñn]o", t)]
    if not primeros:
        return []
    materias: list[tuple[str, int]] = []
    anio = None
    for linea in lineas[primeros[-1]:]:
        if re.match(r"(?i)t[íi]tulo (?:de grado|de pregrado|universitario|final)\b|t[íi]tulo:", linea):
            break
        cabecera = re.fullmatch(r"(?i)(primer|segundo|tercer|cuarto|quinto|sexto)\s+a[ñn]o", linea)
        if cabecera:
            anio = anio_de(linea)
            continue
        fila = re.match(r"^(\d{1,2})\s*\.\s*(\S.*)$", linea)
        if fila and anio:
            _agregar(materias, re.sub(r"\s*\*+\s*$", "", fila.group(2)), anio)
    return desde_el_primero(materias)


def plan_ucsf(html: str) -> list[tuple[str, int]]:
    """The UCSF's career pages, year by year, where a long name is printed as
    two bullets ("– Administración de las" / "– Organizaciones
    Agropecuarias"): a name that ends in a connector goes on in the next of
    the same year."""
    unidas: list[tuple[str, int]] = []
    pendiente: tuple[str, int] | None = None
    for nombre, anio in plan_texto_por_anio(html):
        if pendiente and pendiente[1] == anio:
            nombre = f"{pendiente[0]} {nombre}"
        pendiente = None
        if _CONECTOR_FINAL.search(nombre):
            pendiente = (nombre, anio)
            continue
        unidas.append((nombre, anio))
    return desde_el_primero(unidas) if pendiente is None else []


def plan_unvime(html: str) -> list[tuple[str, int]]:
    """The UNViMe's career pages (Elementor nested tabs): a tab per year
    ("1° Año", "2°", …) and, in the same order, a panel whose lines are the
    year's subjects, each after a "#" bullet. Tabs and panels must be as
    many as each other."""
    soup = BeautifulSoup(html or "", "html.parser")
    for contenedor in soup.select(".e-n-tabs"):
        titulos = [anio_de(_texto(t)) or (int(m.group(1)) if (m := re.match(r"\s*(\d)\s*[°º]", _texto(t))) else None)
                   for t in contenedor.select(".e-n-tabs-heading > .e-n-tab-title")]
        paneles = contenedor.select(".e-n-tabs-content > div")
        if not titulos or len(titulos) != len(paneles) or None in titulos:
            continue
        materias: list[tuple[str, int]] = []
        for anio, panel in zip(titulos, paneles):
            for linea in panel.get_text("\n").split("\n"):
                linea = clean_text(linea)
                if linea and linea != "#" and re.search(r"[A-Za-zÁÉÍÓÚáéíóúñÑ]{3}", linea):
                    _agregar(materias, linea.rstrip("."), anio)
        if materias:
            return desde_el_primero(materias)
    return []


_COLUMNA_DE_CURSOS = re.compile(r"(?i)^(?:cursos?|asignaturas?|materias?)$")
# A row that holds a place for a choice: "Curso Electivo 1", "Electiva 2",
# "Créditos en Historia de la Música", the "Complementaria" of an orientation.
_LUGAR_A_ELEGIR = re.compile(r"(?i)^(?:(?:curso|asignatura|materia)s?\s+)?(?:electiv|optativ)|^cr[ée]ditos\s+en\b"
                             r"|^complementaria$")


def _lo_que_la_precede(tabla: Tag) -> str:
    """The words between a table and the one before it: its heading."""
    partes: list[str] = []
    for texto in tabla.find_all_previous(string=True):
        if texto.find_parent("table") not in (None, tabla):
            break
        partes.append(texto.strip())
        if sum(map(len, partes)) > 300:
            break
    return " ".join(reversed([p for p in partes if p]))


def plan_unq_cursos(html: str) -> list[tuple[str, None]]:
    """UNQ's plans by cycles and núcleos, without years: a table per núcleo
    ("Cursos Básicos del Ciclo Inicial", "Otros requisitos curriculares")
    with a column of courses and one of credits, and its total row. The
    obligatory tables are the plan; a table, or the rows after a heading
    inside one ("Asignaturas Electivas"), of electives is a pool to choose
    from and is left out, and so are the rows that hold a choice's place
    ("Curso Electivo 1").

    Nothing is read when the page cannot be taken whole: a table whose
    rows' credits do not add up to its total is a pool presented as a list
    (Arquitectura Naval's complementary courses: 108 credits listed, 48
    taken); a page with an orientation has its own pool or alternatives
    (Comunicación Social's two); and a table without its heading row is the
    plan going on where the columns are not known (Informática's from the
    sixth term)."""
    leidas: list[tuple[str, int]] = []
    for tabla in BeautifulSoup(html or "", "html.parser").find_all("table"):
        filas = [[_texto(c) for c in fila.find_all(["td", "th"])] for fila in tabla.find_all("tr")]
        filas = [celdas for celdas in filas if any(celdas)]
        if not filas:
            continue
        encabezado = [c.replace("A signatura", "Asignatura") for c in filas[0]]
        if re.search(r"(?i)\borientaci[óo]n\b", _lo_que_la_precede(tabla)[-150:]):
            return []
        cursos = next((i for i, c in enumerate(encabezado) if _COLUMNA_DE_CURSOS.match(c)), None)
        creditos = next((i for i, c in enumerate(encabezado) if re.match(r"(?i)cr[ée]ditos", c)), None)
        if cursos is None or creditos is None:
            if re.search(r"\d", " ".join(encabezado)) and not re.search(r"(?i)total|cr[ée]ditos", encabezado[0]) \
                    or re.fullmatch(r"(?i)\S+\s+(?:cuatrimestre|semestre|a[ñn]o)", encabezado[0]):
                return []
            continue
        # ("Tres cursos, a elegir de las áreas listadas a continuación".)
        if re.search(r"(?i)electiv|optativ|a elegir", _lo_que_la_precede(tabla)[-150:]):
            continue
        suma, nombres, total, electivas = 0, [], None, False
        for celdas in filas[1:]:
            if any(re.match(r"(?i)(?:sub)?total(?:es)?\b", c) for c in celdas):
                total = [int(re.sub(r"\s", "", c)) for c in celdas if re.fullmatch(r"\d[\d\s]{0,3}", c)]
                continue
            llenas = [c for c in celdas if c]
            # A row of one cell is a heading inside the table; the electives
            # after "Núcleo Electivo" run past its "Mención: ..." headings to
            # the next obligatory one ("Otros requisitos").
            if len(llenas) == 1:
                if re.search(r"(?i)electiv|optativ", llenas[0]):
                    electivas = True
                elif re.search(r"(?i)obligatori|requisito|b[áa]sic|orientad|formaci[óo]n general", llenas[0]):
                    electivas = False
                continue
            if electivas or not celdas[cursos]:
                continue
            if len(celdas) != len(encabezado) or not re.fullmatch(r"\d{1,2}", celdas[creditos]):
                return []
            suma += int(celdas[creditos])
            nombres.append(celdas[cursos])
        if total is not None and suma not in total:
            return []
        for nombre in nombres:
            if not _LUGAR_A_ELEGIR.search(nombre):
                # (_agregar keeps a subject with its year; these have none.)
                _agregar(leidas, nombre, -1)
    return [(nombre, None) for nombre, _ in leidas]


_ENCABEZADO_PERIO = re.compile(r"(?i)^(materias?\b|(primer|segundo|tercer)\s+(bimestre|cuatrimestre)$|optativa\b)")


def plan_perio_unlp(html: str) -> list[tuple[str, int]]:
    """UNLP Periodismo's "Asignaturas ..." page of a tecnicatura: a heading
    per year ("Primer año"), its term headings ("Primer cuatrimestre",
    "Materias Obligatorias de cursada cuatrimestral") and a subject per line,
    up to the share links. The "Tramo inicial" (an entry workshop outside the
    years) and the optatives to choose ("Optativa 1", "Optativa I: A/B") are
    not taken; a plan with a ciclo in place of a year is not read."""
    soup = BeautifulSoup(html or "", "html.parser")
    contenido = soup.select_one("article") or soup
    lineas = [clean_text(l) for l in contenido.get_text("\n").split("\n") if clean_text(l)]
    inicio = next((i for i, l in enumerate(lineas) if re.match(r"(?i)^asignaturas\b", l)), None)
    if inicio is None:
        return []
    materias: list[tuple[str, int]] = []
    anio = None
    for linea in lineas[inicio:]:
        if linea.lower() == "facebook":
            break
        if re.match(r"(?i)^(tramo inicial|primer ciclo|segundo ciclo|tercer ciclo)$", linea):
            if "ciclo" in linea.lower():
                return []
            anio = None
            continue
        nuevo = anio_de(linea)
        if nuevo:
            anio = nuevo
        elif anio and not _ENCABEZADO_PERIO.match(linea):
            _agregar(materias, linea, anio)
    return desde_el_primero(materias)
