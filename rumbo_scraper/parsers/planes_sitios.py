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
from collections import Counter

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
    r"|:$|^resoluci[óo]n|deber[áa]|^entre\s+\d|a determinar|^horas flexibles$"
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


def _agregar(materias: list[tuple[str, int]], nombre: str, anio: int | None) -> None:
    nombre = clean_text(nombre).replace("\xa0", " ").strip(" .;-–*")
    # A list's marks and codes: "› Nutrición" (UNAU), "COD: 101 - Guión" (UNMdP FAUD).
    nombre = re.sub(r"^(?:[›•·⏺◻▪■□◦\u2022\ufe0f\ufe0e]\s*)+", "", nombre)
    nombre = re.sub(r"(?i)^cod\.?:?\s*\d*\s*[-–]\s*", "", nombre)
    # Numbered in Roman figures: "VI.- Derecho del Trabajo I", "XI. Inglés I" (UEAN).
    nombre = re.sub(r"^[IVXL]{1,8}\s*\.-?\s*(?=[A-ZÁÉÍÓÚÑ])", "", nombre)
    # "Algebra I (anual)", "Rítmica (Cuatr.)", "Proyecto I Anual", "Matemática 1°C",
    # "(1° Cuatrimestre)", "(2do cuatrimestre)", "(Anual) Créditos 10.00": how long it runs, not its name.
    nombre = re.sub(r"(?i)\s*cr[ée]ditos\s*[\d.,]+\s*$", "", nombre)
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
    titulo = soup.find(lambda e: e.name in ("h2", "h3") and re.match(r"(?i)plan de estudios", _texto(e)))
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
                r"(?i)asignaturas complementarias|dejanos tu consulta|los alumnos que", texto):
            break
        # A year: a heading ("Primer año") or a paragraph of it in bold.
        negrita = elemento.find(["strong", "b"])
        if elemento.name == "h4" or (negrita and _texto(negrita) == texto):
            anio = anio_de(texto) or (anio if elemento.name != "h4" else None)
            continue
        if anio:
            _agregar(materias, texto, anio)
    return desde_el_primero(materias)


_MATERIA_IUPFA = re.compile(r"^\s*\d{2}\s+(\S.*?)\s{2,}(?:ANUAL|CUATRIMESTRAL|SEMESTRAL|BIMESTRAL)\b")


def plan_iupfa(texto_con_columnas: str) -> list[tuple[str, int]]:
    """The Federal Police university's plans (``pdftotext -layout``): a
    heading per year ("PRIMER AÑO"), a row per subject with its code, name
    and term ("01  BALÍSTICA I  ANUAL  128")."""
    materias: list[tuple[str, int]] = []
    anio = None
    for linea in texto_con_columnas.splitlines():
        encabezado = _ANIO_IUCBC.match(linea)
        if encabezado:
            anio = _ORDINALES_UHIBA[encabezado.group(1).lower()]
            continue
        materia = _MATERIA_IUPFA.match(linea)
        if anio and materia:
            _agregar(materias, materia.group(1), anio)
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
_REGIMEN_DNGU = r"(?:Cuatrimestral|Anual|Semestral|Bimestral|Trimestral)"
_FILA_DNGU = re.compile(r"^\s{0,3}(\d{1,3}(?:\.\d{1,2}){0,3}\.?)\s+(.*?)\s*" + _REGIMEN_DNGU + r"\b")
_NO_ES_NOMBRE_DNGU = re.compile(r"(?i)^(COD|CARGA|SEMANAL|HORARIA|MODALIDAD|DICTADO|T[ÍI]TULO|IF-\d|P[áa]gina|"
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
    if "ASIGNATURA" not in texto_con_columnas or not any(map(_ANIO_DNGU.match, texto_con_columnas.splitlines())):
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
        if re.match(r"^\s*T[ÍI]TULO:", linea) and filas:
            break
        fila = _FILA_DNGU.match(linea)
        if fila and anio:
            filas.append({"anio": anio, "nombre": clean_text(fila.group(2)), "antes": list(sueltas), "despues": []})
            sueltas = []
            continue
        texto = clean_text(linea)
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
        if (fila["nombre"] and fila["antes"] and not conectan) or not partes or len(fila["antes"]) > 2:
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
    r"^c[áa]tedra\s+[a-z]\b|^ver\s+plan|^obtiene\s+t[íi]tulo|^comienzan|^documentaci|^dni\b|"
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
    rotulo = next((k for k, l in enumerate(bloque) if re.match(r"(?i)^denominaci[óo]n\s*:", l)), None)
    if rotulo is not None:  # a labelled name runs to its "Formato:"
        bloque = bloque[rotulo:]
    while rotulo is None and len(bloque) > 1 and not (all(not l.endswith(".") for l in bloque[:-1])
                                   and all(_CONECTOR_FINAL.search(a) or b[:1].islower()
                                           for a, b in zip(bloque, bloque[1:]))):
        bloque.pop(0)
    titulo = re.sub(r"\.\s+(I{1,3})$", r" \1", " ".join(bloque).strip().rstrip(".").strip())
    if titulo.isupper():
        titulo = titulo[:1] + titulo[1:].lower()
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
        if not re.match(r"(?i)^formato\s*:", linea):
            continue
        siguientes = [l for l in lineas[i + 1:i + 30] if l and not _PIE_DISENO.match(l)][:5]
        ubicacion = next((l for l in siguientes if re.match(r"(?i)^ubicaci[óo]n (sugerida )?en el dise[ñn]o", l)), "")
        ano = re.search(r"(?i)\b(primer|segundo|tercer|cuarto|quinto|[1-5])\s*[°º]?\s*a[ñn]o\b", ubicacion)
        titulo = re.sub(r"(?i)^denominaci[óo]n\s*:\s*", "", _titulo_de_unidad(lineas, i))
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
