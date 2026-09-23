"""Reading a university catalogue from what its pages say, not where they sit.

Every per-site adapter in this package starts by learning the addresses a
particular university uses for its careers. That knowledge is worth having for
fifteen universities and impossible to have for a hundred.

This reader does without it. An Argentine university cannot invent the name of
a degree: the Ministry recognises a closed set of them, and the university
prints the recognised name as the heading of the page that offers it. So a
page whose heading reads "Licenciatura en Psicología" is a career page at any
university in the country, and the word "Licenciatura" also says it is a
degree rather than a master's. Everything here follows from that.

What it reads is therefore narrower than what an adapter reads, and it is
honest about the difference: the name, the level, the award, the length, the
mode of study and the plan of studies where the page publishes one as a list.
Anything a site states in its own private shape stays for an adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from rumbo_scraper.catalogo import Universidad
from rumbo_scraper.contracts import SECTION_FIELDS, blank_record
from rumbo_scraper.normalizers.text import clean_text, comparison_key

# The degrees the country recognises, the level each one belongs to and, for a
# postgraduate degree, the kind the schema stores. A name is matched at its
# start, because "Licenciatura en Economía" is a degree and "Ingreso a la
# Licenciatura" is a page about admission to one.
DEGREES: tuple[tuple[str, str, str | None], ...] = (
    (r"doctorado(?:s)?\b|doctor(?:ado)? en\b", "Posgrado", "Doctorado"),
    (r"maestr[íi]a(?:s)?\b|mag[íi]ster\b|m\.?b\.?a\.?\b|master\b", "Posgrado", "Maestría"),
    (r"especializaci[óo]n(?:es)?\b|especialista en\b|carrera de especializaci",
     "Posgrado", "Especialización"),
    (r"diplomatura(?:s)?\b|diploma(?:do)?\s+(?:superior|de posgrado|en)\b",
     "Posgrado", "Diplomatura"),
    (r"tecnicatura(?:s)?\b|t[ée]cnic[oa]\s+(?:universitari|superior)",
     "Pregrado", None),
    (r"licenciatura(?:s)?\b|licenciad[oa] en\b", "Grado", None),
    (r"ingenier[íi]a(?:s)?\b", "Grado", None),
    (r"profesorado(?:s)?\b", "Grado", None),
    (r"ciclo\s+(?:de\s+)?(?:licenciatura|complementaci[óo]n)", "Grado", None),
)

# A degree the country lets a university name by its subject alone. These are
# only read at the head of a name, because the subject also turns up inside
# the name of things that are not degrees: "Agente de Propaganda Médica" is a
# course an extension office runs, not the career of Medicina.
SELF_NAMED: tuple[str, ...] = (
    r"abogac[íi]a", r"arquitectura", r"medicina", r"m[ée]dic[oa] veterinari",
    r"veterinaria", r"odontolog[íi]a", r"farmacia", r"bioqu[íi]mica",
    r"psicolog[íi]a", r"psicopedagog[íi]a", r"enfermer[íi]a", r"obstetricia",
    r"kinesiolog[íi]a", r"fonoaudiolog[íi]a", r"nutrici[óo]n",
    r"contador(?:a)? p[úu]blic[oa]?", r"traductorado",
    r"traductor(?:a)? p[úu]blic[oa]?",
    r"notariado", r"escriban[íi]a", r"dise[ñn]o\s+(?:gr[áa]fico|industrial|"
    r"textil|de indumentaria|de interiores|multimedial)",
)
_AUTONOMOS = tuple(re.compile(rf"^(?:carrera de\s+)?(?:{pattern})\b")
                   for pattern in SELF_NAMED)

# A heading that names a degree but is not the page of one: an index, a piece
# of news, a form, an admission page.
_NOT_A_PROGRAMME = re.compile(
    r"(?i)^(oferta|carreras?|nuestras?|todas? las|conoc[ée]|estudi[áa]\b|"
    r"inscripci|admisi[óo]n|ingreso|preinscrip|novedad|noticia|resultado|"
    r"informaci[óo]n|requisitos?|aranceles?|calendario|listado|[íi]ndice|"
    r"plan de estudios|equivalencias|cambio de|"
    # The page that lists what a career teaches is not a second career.
    r"asignaturas?\s+(?:de|del)\b|materias?\s+(?:de|del)\b|"
    r"correlativ|programas?\s+(?:de|del)\s+(?:las|los)\b|"
    # A headline is about the people of a degree, not about the degree.
    r"(?:l[oa]s )?(?:estudiantes|alumn[oa]s|docentes|egresad[oa]s|"
    r"graduad[oa]s|investigador)\b|"
    # An academic unit is not one of the degrees it teaches.
    r"(?:instituto|departamento|facultad|escuela|centro|secretar[íi]a|"
    r"direcci[óo]n)\s+(?:de|del|en)\b|"
    # What a faculty does besides teaching is not one of its degrees.
    r"(?:investigaci[óo]n|extensi[óo]n|transferencia|vinculaci[óo]n|"
    r"posgrados?|graduad[oa]s|biblioteca|bienestar)\b)"
)
# A verb in the third person turns the name of a degree into the report of
# something that happened to it.
_UNA_NOTICIA = re.compile(
    r"(?i)\b(visit[óa]n?|gan[óa]ron?|present[óa]ron?|inaugur|recib[íi]|"
    r"celebr|cumpl[íi]|lanz[óa]|expus|dict[óa]|brind[óa]|organiz[óa]|"
    r"debat|analiz|festej)\w*\b"
)
# A heading that is a sentence about a degree rather than the name of one.
# Each stem carries its own ending: "comenz" has to match "comenzaron", and
# a bare \b after the stem matches none of the forms a headline uses.
_A_SENTENCE = re.compile(
    r"(?i)\b(se|ya|hoy|nuevo|nueva|abre|abri[óo]|cerr\w*|present\w*|"
    r"gradu\w*|firm\w*|particip\w*|realiz\w*|comenz\w*|convoc\w*|"
    r"entreg\w*|inici\w*|finaliz\w*|dict\w*)\b"
)


@dataclass(frozen=True)
class Programa:
    """A programme page, once its heading has been recognised."""

    nombre: str
    nivel: str
    tipo_posgrado: str | None
    url: str


def _soup(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style", "noscript"]):
        element.decompose()
    return soup


def clasificar(nombre: str) -> tuple[str, str | None] | None:
    """The level and, for a postgraduate degree, the kind a name declares.

    The degree word is looked for anywhere in the name, not only at its start,
    because a university writes both "Licenciatura en Turismo" and "Turismo -
    Licenciatura". It is the presence of the recognised word that makes the
    name a degree; the first one to match decides, and they are ordered so
    that the postgraduate degrees are tried before the undergraduate ones.
    """
    key = comparison_key(nombre)
    if not key:
        return None
    for pattern, level, kind in DEGREES:
        if re.search(pattern, key):
            return level, kind
    for pattern in _AUTONOMOS:
        if pattern.match(key):
            return "Grado", None
    return None


# A heading that is the degree word and nothing else names the index of the
# degrees, not one of them: "Licenciaturas", "Profesorado", "Tecnicatura
# universitaria". A degree is a degree in something.
_SOLO_EL_GRADO = re.compile(
    r"^(?:carreras? de\s+)?(?:licenciatura|ingenieria|profesorado|tecnicatura|"
    r"maestria|doctorado|especializacion|diplomatura|posgrado|grado|pregrado)"
    r"s?(?:\s+universitari[ao]s?)?$"
)
# A plural degree at the head of a name gathers several of them under one
# page, so the page is a list and its heading is not a programme.
_EN_PLURAL = re.compile(
    r"^(?:licenciaturas|ingenierias|profesorados|tecnicaturas|maestrias|"
    r"doctorados|especializaciones|diplomaturas)\b"
)
# What a page announces after a colon when it is about a programme rather
# than being one: an event, a call, a single class.
_UN_EVENTO = re.compile(
    r"(?i):\s*(actividad|jornada|taller|charla|clase|encuentro|convocatoria|"
    r"seminario abierto|muestra|concurso|llamado)"
)


def es_programa(nombre: str) -> bool:
    """Whether a heading names a programme rather than talking about one."""
    if not (6 <= len(nombre) <= 110):
        return False
    # An exclamation is an advertisement: "¡Estudiá Ingeniería en 2018!".
    if "!" in nombre or "¡" in nombre:
        return False
    key = comparison_key(nombre).lstrip("¡¿\"'«-–— ")
    if _UNA_NOTICIA.search(key):
        return False
    # The short form of a department, which only a heading about the
    # department itself carries.
    if re.search(r"\bd(?:e)?pto\b|\bdepto\.", key):
        return False
    if _NOT_A_PROGRAMME.match(key) or _SOLO_EL_GRADO.match(key) or _EN_PLURAL.match(key):
        return False
    if _UN_EVENTO.search(nombre):
        return False
    if _A_SENTENCE.search(key):
        return False
    # A name is a name, not a paragraph: a full stop mid-heading, or more than
    # a dozen words, means the page is describing the degree, not naming it.
    if nombre.count(".") > 1 or len(nombre.split()) > 14:
        return False
    return clasificar(nombre) is not None


def encabezado(html: str) -> str:
    """The name a page gives itself.

    The first heading is preferred to the title of the window because a site
    appends its own name to the title, and sometimes the whole navigation.
    """
    soup = _soup(html)
    for tag in ("h1", "h2"):
        for heading in soup.find_all(tag):
            value = clean_text(heading.get_text(" ", strip=True))
            if es_programa(value):
                return value
    for meta in soup.find_all("meta"):
        if (meta.get("property") or meta.get("name")) == "og:title":
            value = _sin_sufijo(clean_text(str(meta.get("content") or "")))
            if es_programa(value):
                return value
    if soup.title:
        value = _sin_sufijo(clean_text(soup.title.get_text(" ", strip=True)))
        if es_programa(value):
            return value
    return ""


_SEPARADOR = re.compile(r"\s+[|–—-]\s+")


def _sin_sufijo(titulo: str) -> str:
    """The title of a window without the name of the site appended to it."""
    parts = [part for part in _SEPARADOR.split(titulo) if clean_text(part)]
    for part in parts:
        if es_programa(clean_text(part)):
            return clean_text(part)
    return clean_text(parts[0]) if parts else ""


# What a page appends to the name of a programme when it is announcing one
# intake of it. Two intakes of the same degree are the same degree.
_UNA_COHORTE = re.compile(
    r"(?i)\s*[:\-–—]\s*(cohorte|inscripci[óo]n|inscripciones|convocatoria|"
    r"edici[óo]n|ciclo|ingreso|comisi[óo]n|"
    # A site that gives each section of a career its own page repeats the
    # name of the career at the head of every one of them.
    r"cuerpo acad[ée]mico|autoridades|plan de estudios?|perfil|alcances|"
    r"contacto|aranceles?|becas|requisitos|t[íi]tulo|salida laboral|"
    r"campo (?:laboral|profesional)|objetivos|presentaci[óo]n)\b.*$"
)


def sin_cohorte(nombre: str) -> str:
    """The name of a programme without the section of the site it sits in.

    A university that gives the plan, the staff and the fees of a career a
    page each heads every one of them with the name of the career and the
    name of the section, and so does one that announces each intake apart.
    Neither makes a second career.
    """
    recortado = clean_text(_UNA_COHORTE.sub("", nombre))
    return recortado if len(recortado) >= 6 else clean_text(nombre)


def leer_programa(html: str, url: str) -> Programa | None:
    """The programme a page offers, when its heading names one."""
    name = sin_cohorte(encabezado(html))
    if not name:
        return None
    classified = clasificar(name)
    if not classified:
        return None
    level, kind = classified
    return Programa(nombre=name, nivel=level, tipo_posgrado=kind, url=url)


# ---------------------------------------------------------------- the facts

# What a site calls each fact, however it writes the label. A label is only
# recognised where it introduces a value, so "Inicio" alone is not a date: it
# is the first crumb of the trail back to the home page, on every page of
# every site in the country.
FACT_LABELS: tuple[tuple[str, str], ...] = (
    ("titulacion", r"t[íi]tulo(?:s)?(?:\s+(?:oficial|final|de grado|acad[ée]mico|"
                   r"que se otorga|que otorga|a obtener|otorgado))?|"
                   r"titulaci[óo]n|grado acad[ée]mico|certificaci[óo]n"),
    ("duracion", r"duraci[óo]n(?: de la carrera| estimada| total)?|extensi[óo]n|"
                 r"a[ñn]os de cursada|cantidad de a[ñn]os|carga horaria total|"
                 r"duracion aproximada"),
    ("modalidad", r"modalidad(?: de cursada| de dictado| de estudio)?|"
                  r"cursada|dictado|tipo de cursado|forma de cursado"),
    ("inicio", r"inicio de (?:cursada|clases|actividades)|pr[óo]xim[oa] (?:inicio|cohorte)|"
               r"comienzo de (?:cursada|clases)|inicia(?: el)?|cohorte"),
    ("resolucion", r"resoluci[óo]n(?: ministerial| del ministerio)?|"
                   r"reconocimiento oficial|acreditaci[óo]n|coneau|validez nacional"),
    ("turno", r"turno(?:s)?(?: de cursada)?|horario(?:s)?(?: de cursada)?|banda horaria"),
    ("sede", r"sede(?:s)?(?: de cursada)?|localizaci[óo]n|d[óo]nde se cursa|"
             r"lugar de cursada|campus"),
    ("facultad", r"unidad acad[ée]mica|facultad|departamento acad[ée]mico|"
                 r"escuela|dependencia"),
    ("arancel", r"arancel(?:es)?|cuota(?: mensual)?|valor de la cuota|inversi[óo]n"),
    ("nivel", r"nivel(?: acad[ée]mico)?|tipo de carrera"),
)
_LABEL_PATTERNS = tuple(
    (key, re.compile(rf"^(?:{pattern})\s*:?\s*$", re.I)) for key, pattern in FACT_LABELS
)
_INLINE_PATTERNS = tuple(
    (key, re.compile(rf"^(?:{pattern})\s*[:：]\s*(?P<value>.+)$", re.I))
    for key, pattern in FACT_LABELS
)
# A value that is punctuation, a crumb or an invitation is not a value.
_NO_ES_VALOR = re.compile(r"(?i)^(»|>|-|–|\||ver m[áa]s|consultar|pr[óo]ximamente|"
                          r"a confirmar|s/d|n/a)\s*$")


def _clasificar_etiqueta(texto: str) -> str | None:
    key = comparison_key(texto)
    for name, pattern in _LABEL_PATTERNS:
        if pattern.match(key):
            return name
    return None


def _lineas(soup: BeautifulSoup) -> list[str]:
    """The page as the lines a reader sees.

    A site writes its facts one per line inside a single element, separated by
    a line break rather than by markup: four facts about a career arrive as
    one string unless the breaks are turned back into lines first.
    """
    for element in soup.find_all("br"):
        element.replace_with("\n")
    return [clean_text(line) for line in soup.get_text("\n").split("\n")]


_ACCESORIOS = ("[class*=breadcrumb], [class*=migas], [id*=breadcrumb], "
               "[class*=sidebar], [class*=lateral], [role=navigation]")


def _quitar_accesorios(soup: BeautifulSoup) -> None:
    """Remove the trail of crumbs and the side column, and nothing else.

    Matching a class by substring is the only way to find these across sites
    that name them differently, and it has one trap: the page builders most
    universities use write the same words into the class of the body itself,
    so an unguarded sweep deletes the whole document. An element is therefore
    only removed when it is not the document and does not contain its
    heading.
    """
    heading = soup.find("h1")
    for element in soup.select(_ACCESORIOS):
        if element.name in ("body", "html") or element.parent is None:
            continue
        if heading is not None and heading in element.descendants:
            continue
        element.decompose()


def leer_datos(html: str) -> dict[str, str]:
    """Read the facts a programme page prints beside its name.

    Four shapes cover nearly every site: a definition list, a table of two
    columns, a label element followed by its value, and a line that writes
    "Duración: 5 años" in one breath. The navigation is removed first: it
    names a faculty on every page of the site, and the faculty of the page is
    the one the page states, not the one its menu happens to link to.
    """
    soup = _soup(html)
    for element in soup(["nav", "footer", "header", "aside", "form", "select"]):
        element.decompose()
    _quitar_accesorios(soup)
    facts: dict[str, str] = {}

    def offer(key: str | None, value: str) -> None:
        value = clean_text(value).strip(" :-–|")
        if not key or key in facts:
            return
        if not (1 <= len(value) <= 300) or _NO_ES_VALOR.match(value):
            return
        facts[key] = value

    for term in soup.find_all("dt"):
        definition = term.find_next_sibling("dd")
        if definition is not None:
            offer(_clasificar_etiqueta(term.get_text(" ", strip=True)),
                  definition.get_text(" ", strip=True))

    for row in soup.find_all("tr"):
        cells = row.find_all(["th", "td"], recursive=False)
        if len(cells) == 2:
            offer(_clasificar_etiqueta(cells[0].get_text(" ", strip=True)),
                  cells[1].get_text(" ", strip=True))

    for element in soup.find_all(["strong", "b", "span", "h3", "h4", "h5", "dt", "label"]):
        text = clean_text(element.get_text(" ", strip=True))
        if not text or len(text) > 60:
            continue
        key = _clasificar_etiqueta(text)
        if not key:
            continue
        sibling = element.find_next_sibling()
        if sibling is not None:
            offer(key, sibling.get_text(" ", strip=True))

    # "Duración: 5 años", written as one line among several in one element.
    for line in _lineas(soup):
        if not line or len(line) > 200:
            continue
        for key, pattern in _INLINE_PATTERNS:
            match = pattern.match(line)
            if match:
                offer(key, match.group("value"))
    return facts


def descripcion(html: str) -> str | None:
    """The sentence a page publishes about itself."""
    for meta in _soup(html).find_all("meta"):
        if (meta.get("name") or meta.get("property")) in ("description", "og:description"):
            value = clean_text(str(meta.get("content") or ""))
            if 40 <= len(value) <= 600:
                return value
    return None


_ANIOS = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:\(\w+\)\s*)?a[ñn]os?", re.I)
_CUATRI = re.compile(r"(\d+)\s*cuatrimestres?", re.I)
_MESES = re.compile(r"(\d+)\s*meses", re.I)


def duracion_anios(value: str | None) -> float | None:
    """How many years a programme lasts, when the page states it in years."""
    match = _ANIOS.search(value or "")
    if match:
        years = float(match.group(1).replace(",", "."))
        return years if 0 < years <= 12 else None
    match = _CUATRI.search(value or "")
    if match:
        terms = int(match.group(1))
        return round(terms / 2, 1) if 0 < terms <= 24 else None
    return None


def duracion_meses(value: str | None) -> int | None:
    match = _MESES.search(value or "")
    if match:
        months = int(match.group(1))
        return months if 0 < months <= 120 else None
    match = _CUATRI.search(value or "")
    if match:
        terms = int(match.group(1))
        return terms * 6 if 0 < terms <= 24 else None
    years = duracion_anios(value)
    return round(years * 12) if years else None


def modalidad(value: str | None) -> str | None:
    key = comparison_key(value)
    if not key:
        return None
    remote = any(word in key for word in ("distancia", "online", "virtual", "remoto"))
    in_person = "presencial" in key and "semipresencial" not in key
    if "semipresencial" in key or "hibrid" in key or "blended" in key \
            or (in_person and remote):
        return "Híbrida"
    if in_person:
        return "Presencial"
    if remote:
        return "Virtual"
    return None


_CONEAU = re.compile(
    r"(?i)(?:res(?:oluci[óo]n)?\.?\s*(?:n[°ºo]\.?\s*)?)"
    r"((?:me|men|cs|rm|ct)?[\s.-]*\d{1,5}\s*/\s*\d{2,4})"
)


# A ministry writes its own resolution without the word: "ME N° 1543/2021".
_NUMERO_SOLO = re.compile(r"\b(\d{1,5}\s*/\s*\d{2,4})\b")


def resolucion(value: str | None) -> str | None:
    """The number of the resolution that recognises a programme."""
    text = clean_text(value)
    match = _CONEAU.search(text)
    if match:
        return clean_text(match.group(1))
    # Only where the value is short enough to be the resolution itself: a
    # paragraph holds many numbers with a slash and most are dates.
    if len(text) <= 40:
        match = _NUMERO_SOLO.search(text)
        if match:
            return clean_text(match.group(1))
    return None


# ------------------------------------------------------------------ the plan

# How a site writes the year a subject is taught in. Both orders occur:
# "Primer año" and "Año 1", and the ordinals are written as words as often as
# they are written as digits.
_ORDINALES = {
    "primer": 1, "primero": 1, "1": 1, "1er": 1, "1ro": 1, "i": 1,
    "segundo": 2, "2": 2, "2do": 2, "ii": 2,
    "tercer": 3, "tercero": 3, "3": 3, "3er": 3, "3ro": 3, "iii": 3,
    "cuarto": 4, "4": 4, "4to": 4, "iv": 4,
    "quinto": 5, "5": 5, "5to": 5, "v": 5,
    "sexto": 6, "6": 6, "6to": 6, "vi": 6,
    "septimo": 7, "7": 7, "7mo": 7, "vii": 7,
}
_ANIO_ADELANTE = re.compile(
    r"^(?:ciclo\s+)?(" + "|".join(sorted(_ORDINALES, key=len, reverse=True))
    + r")[°ºa-z]*\s+(?:a[ñn]o|nivel)\b"
)
_ANIO_ATRAS = re.compile(
    r"^(?:a[ñn]o|nivel|curso)\s*[:n°º]*\s*("
    + "|".join(sorted(_ORDINALES, key=len, reverse=True)) + r")\b"
)


def anio_de(texto: str) -> int | None:
    """The year of study a heading announces, when it announces one."""
    key = comparison_key(texto).strip(" :.-")
    if not key or len(key) > 40:
        return None
    for pattern in (_ANIO_ADELANTE, _ANIO_ATRAS):
        match = pattern.match(key)
        if match:
            return _ORDINALES.get(match.group(1))
    return None


# What a plan prints that is not a subject.
_NO_ES_MATERIA = re.compile(
    r"(?i)^(total|carga|horas?|cr[ée]ditos?|c[óo]digo|asignatura|materia|"
    r"a[ñn]o|nivel|cuatrimestre|semestre|correlativ|r[ée]gimen|obligatori|"
    r"electiv[ao]s?$|optativ[ao]s?$|plan de estudio|t[íi]tulo|ver m[áa]s|"
    r"descargar|inscrip|requisit|cantidad|sub ?total|duraci[óo]n|modalidad|"
    r"turno|cursada|contacto|sede|autoridad|arancel|beca|novedad|perfil|"
    r"alcances|programas? para|men[úu]|compartir|imprimir|cursos?\b|"
    r"presencial|virtual|a distancia|anual$|bimestral|trimestral|"
    # "PRIMER CUATRIMESTRE" divides the year; it is not taught.
    r"(?:primer|segundo|tercer|cuarto|quinto|sexto)[oa]?\s+"
    r"(?:cuatrimestre|semestre|a[ñn]o|nivel|m[óo]dulo|ciclo|bimestre|"
    r"trimestre|per[íi]odo))"
)

# The word a line opens with when it is the middle of a sentence the page
# broke across lines, not the name of anything. The articles are in the list
# too, which costs the occasional real subject named "El Derecho Procesal";
# Argentine plans name that subject "Derecho Procesal", and a missing subject
# is easier to live with than a paragraph filed as one.
_ARRANCA_EN_MEDIO = frozenset(
    "de del la el los las y e o u que con para en se su sus al a por un una "
    "como sobre entre desde hasta este esta estos estas".split()
)

# The section a career page opens once its plan is over. The plan ends there,
# and a page that writes its plan as plain lines gives no other sign of where.
_FIN_DEL_PLAN = re.compile(
    r"(?i)^(contacto|cursada|autoridades?|sedes?|aranceles?|inscripci[óo]n|"
    r"becas|novedades|perfil del|alcances|requisitos|t[íi]tulos?|descarg|"
    r"programas? para descargar|m[áa]s informaci[óo]n|pr[áa]cticas|"
    r"salida laboral|campo (?:laboral|profesional)|objetivos)"
)


def es_materia(nombre: str) -> bool:
    """Whether a line of a plan names a subject.

    A plan prints its own scaffolding -- the word "Asignatura" over the
    column, the hours beside it, the total under it -- and a subject is what
    is left once that is set aside: a few words, mostly letters, that do not
    announce a column or a sum.
    """
    text = clean_text(nombre)
    if not (4 <= len(text) <= 90):
        return False
    if _NO_ES_MATERIA.match(comparison_key(text)):
        return False
    letters = sum(char.isalpha() for char in text)
    if letters < 4 or letters < len(text) * 0.5:
        return False
    # A line that ends in a comma, opens a bracket it never closes, or begins
    # where a sentence was cut, is one piece of a paragraph the page broke
    # across lines rather than the name of a subject.
    if text.endswith((",", ";", ":")) or text.count("(") != text.count(")"):
        return False
    if text[0] in ",;.)":
        return False
    if comparison_key(text.split()[0]) in _ARRANCA_EN_MEDIO:
        return False
    # A sentence is not a subject: a subject is named, not described.
    return len(text.split()) <= 12


# No career in the country teaches more than this in one year. A block that
# yields more is not a year of a plan: the reader has run past the end of it
# and into the rest of the page.
MAX_POR_ANIO = 30
MAX_POR_PLAN = 120


def leer_plan(html: str) -> list[dict[str, Any]]:
    """Read the plan of studies a page publishes under each year of study.

    The page is read as the lines a person sees rather than as a tree of
    elements, because half the universities give each subject an element of
    its own and the other half write the whole year into one paragraph with a
    line break between subjects. Flattened to lines, both look the same.

    A year opens a block and the next year closes it, as does the heading of
    whatever the page says after the plan and any line long enough to be
    prose. A plan that publishes no year at all is not read: without the year
    its rows cannot be told from any other list on the page, and a page
    carries many.
    """
    soup = _soup(html)
    for element in soup(["nav", "footer", "header", "aside", "form", "select"]):
        element.decompose()
    _quitar_accesorios(soup)

    subjects: list[dict[str, Any]] = []
    seen: set[tuple[int, str]] = set()
    year: int | None = None
    en_el_anio = 0
    for line in _lineas(soup):
        if not line:
            continue
        if len(line) <= 40 and anio_de(line) is not None:
            year, en_el_anio = anio_de(line), 0
            continue
        if year is None:
            continue
        if len(line) <= 60 and _FIN_DEL_PLAN.match(line):
            year = None
            continue
        if len(line) > 160:
            # Prose: the plan is over, whatever the page calls what follows.
            year = None
            continue
        name = _sin_vineta(line)
        if not es_materia(name):
            continue
        en_el_anio += 1
        if en_el_anio > MAX_POR_ANIO:
            # No year of any career teaches this much. The reader has walked
            # past the end of the plan, so nothing it read can be trusted.
            return []
        key = (year, comparison_key(name))
        if key in seen:
            continue
        seen.add(key)
        subjects.append({"nombre": name, "anio": year})
    if not (4 <= len(subjects) <= MAX_POR_PLAN):
        return []
    return subjects


# The mark a page puts before each subject, and the number it sometimes puts
# there instead.
_VINETA = re.compile(r"^(?:[•·▪◦‣*\-–—]|\d{1,3}[.)°]|[a-z][.)])\s+")


def _sin_vineta(linea: str) -> str:
    return clean_text(_VINETA.sub("", clean_text(linea)))



# ------------------------------------------------------------- the addresses

# An address that cannot hold a programme page: a file, a search, a login, an
# archive of news. Fetching them is what makes a crawl slow.
_NO_ES_PAGINA = re.compile(
    r"(?i)\.(pdf|docx?|xlsx?|pptx?|jpe?g|png|gif|svg|webp|zip|rar|mp[34]|avi)$"
    r"|/(wp-admin|wp-json|wp-content|feed|rss|tag|tags|author|category|"
    r"buscar|search|login|ingresar|carrito|cart|comment)\b"
    r"|[?&](replytocom|share|print)="
)
# The part of a site that holds its catalogue. A university publishes hundreds
# of pages of news for every page of a career, and the address says which is
# which long before the page is downloaded.
_PUEDE_SER_CATALOGO = re.compile(
    r"(?i)/(carrera|carreras|grado|pregrado|posgrado|postgrado|oferta|"
    r"academic|propuesta|estudi|licenciatura|ingenieria|profesorado|"
    r"tecnicatura|maestria|doctorado|especializacion|diplomatura|"
    r"facultad|escuela|departamento|unidad)"
)


def es_del_dominio(url: str, dominios: tuple[str, ...]) -> bool:
    """Whether an address belongs to the university, subdomains included.

    A national university does not keep its catalogue on one host: each
    faculty publishes its own careers on a host of its own under the domain
    of the university. Reading only the main host would find the list of the
    faculties and none of the careers.
    """
    host = (urlparse(url).netloc or "").lower().split(":")[0]
    host = host[4:] if host.startswith("www.") else host
    return any(host == dominio or host.endswith("." + dominio)
               for dominio in dominios)


def enlaces(html: str, pagina: str, dominios: tuple[str, ...]) -> list[str]:
    """Every address of the university a page links to."""
    found: list[str] = []
    seen: set[str] = set()
    for anchor in _soup(html).find_all("a", href=True):
        href = clean_text(anchor["href"])
        if not href or href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        url = urljoin(pagina, href).split("#")[0].rstrip("/")
        if not url.startswith("http") or not es_del_dominio(url, dominios):
            continue
        if _NO_ES_PAGINA.search(url) or url in seen:
            continue
        seen.add(url)
        found.append(url)
    return found


def parece_catalogo(url: str) -> bool:
    """Whether an address belongs to the part of a site that holds careers."""
    return bool(_PUEDE_SER_CATALOGO.search(urlparse(url).path))


def direcciones_del_sitemap(xml: str) -> list[str]:
    """Every address a sitemap lists, including the sitemaps it points to."""
    return [clean_text(url) for url in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml or "")]


# ---------------------------------------------------------------- the dataset

# What the value of an academic unit cannot be: a sentence, an address, a
# link. The value itself is trusted because the page wrote a label over it.
_NO_ES_UNIDAD = re.compile(r"(?i)https?://|@|\d{4}|^(ver|consultar|todas?|varias?)\b")
# An office of the rectorate runs courses, but the schema files an academic
# unit as a facultad, a escuela, a departamento or a centro, and a secretaría
# is none of those. Naming one would be filing it under a kind it is not.
_NO_ES_ACADEMICA = re.compile(
    r"^(secretar[íi]a|prosecretar[íi]a|direcci[óo]n|rectorado|subsecretar[íi]a|"
    r"[áa]rea|programa|oficina|coordinaci[óo]n)\b")


def nombre_facultad(value: str | None) -> str | None:
    """The academic unit a page states under its own label.

    The name is not required to begin with "Facultad": a national university
    is as likely to teach through a Departamento or an Escuela, and several
    of them name the unit by its subject alone -- "Ciencia y Tecnología".
    What makes the value trustworthy is that the page labelled it, not the
    shape of the words.
    """
    text = clean_text(value)
    if not (4 <= len(text) <= 90) or len(text.split()) > 10:
        return None
    if _NO_ES_UNIDAD.search(text) or _NO_ES_ACADEMICA.match(comparison_key(text)):
        return None
    return text


def build_dataset(
    universidad: Universidad,
    programas: list[Programa],
    paginas: dict[str, str],
    planes: dict[str, list[dict[str, Any]]],
    errores: list[dict[str, str]] | None = None,
    descubiertas: int = 0,
) -> dict[str, Any]:
    """Assemble the contract from the pages that turned out to be programmes."""
    data: dict[str, list[dict[str, Any]]] = {section: [] for section in SECTION_FIELDS}
    name = universidad.nombre_oficial
    data["universidades"] = [blank_record(
        "universidades", nombre_oficial=name, nombre_corto=universidad.nombre_corto,
        tipo_gestion=universidad.tipo_gestion, sitio_web=universidad.sitio_web,
    )]
    data["localidades"] = [blank_record(
        "localidades", nombre_localidad=universidad.localidad,
        provincia=universidad.provincia,
    )]

    dominios = (universidad.dominio,) + tuple(universidad.dominios_extra)
    faculties: set[str] = set()
    excluded: list[dict[str, str]] = []
    seen: dict[str, str] = {}
    detail: list[dict[str, Any]] = []
    personas: dict[str, dict[str, Any]] = {}
    canales: dict[str, dict[str, Any]] = {}
    for programme in _sin_recortes(programas, excluded):
        key = comparison_key(programme.nombre)
        if key in seen:
            excluded.append({"programa": programme.nombre, "url": programme.url,
                             "motivo": f"ya figura en {seen[key]}"})
            continue
        seen[key] = programme.url
        html = paginas.get(programme.url, "")
        facts = leer_datos(html)
        faculty = nombre_facultad(facts.get("facultad"))
        if faculty:
            faculties.add(faculty)
        # The page states the level under a label of its own, and what it
        # states beats what the name of the degree implies: a "Licenciatura"
        # that the university files under Pregrado is a Pregrado.
        level = _nivel_publicado(facts.get("nivel")) or programme.nivel
        if level == "Posgrado" and not programme.tipo_posgrado:
            level = programme.nivel
        detail.append({"nombre": programme.nombre, "nivel": level,
                       "url": programme.url, **facts})
        for person in leer_autoridades(html):
            if not faculty:
                continue
            personas.setdefault(comparison_key(person["nombre"] + person["cargo"]), {
                "facultad_nombre": faculty, "carrera": programme.nombre,
                "cargo": person["cargo"], "tipo": person["tipo"],
                "nombre_autoridad": person["nombre"],
            })
        for channel in leer_contactos(html, dominios):
            canales.setdefault(channel["usuario_o_direccion"], {
                "facultad_nombre": faculty, **channel})

        if level == "Posgrado":
            data["posgrados"].append(blank_record(
                "posgrados", universidad_nombre=name, facultad_nombre=faculty,
                nombre_programa=programme.nombre,
                tipo_posgrado=programme.tipo_posgrado,
                titulo_otorgado=_titulo(facts.get("titulacion")), sede=None,
                modalidad=modalidad(facts.get("modalidad")),
                duracion_meses=duracion_meses(facts.get("duracion")),
                requiere_tesis_trabajo_final=None, requisito_titulo_previo=None,
                cohorte_inicio=facts.get("inicio"), costo_total_programa=None,
                moneda=None, descripcion_breve=descripcion(html),
                url_oficial=programme.url,
            ))
        else:
            subjects = planes.get(programme.url) or []
            data["carreras"].append(blank_record(
                "carreras", universidad_nombre=name, facultad_nombre=faculty,
                nombre_carrera=programme.nombre,
                denominacion_canonica=programme.nombre, nivel=level,
                titulo_otorgado=_titulo(facts.get("titulacion")),
                tiene_titulo_intermedio=None,
                duracion_anios=duracion_anios(facts.get("duracion")),
                descripcion_breve=descripcion(html),
                cantidad_materias_total=len(subjects) or None,
            ))
            data["ofertas"].append(blank_record(
                "ofertas", universidad_nombre=name, facultad_nombre=faculty,
                carrera_nombre=programme.nombre, sede=None,
                modalidad=modalidad(facts.get("modalidad")), regimen_ingreso=None,
                coneau_resolucion=resolucion(facts.get("resolucion")),
                coneau_vigencia_hasta=None, tiene_pasantias=None,
                tiene_bolsa_trabajo=None, url_oficial=programme.url,
            ))
        for subject in planes.get(programme.url) or []:
            data["materias"].append(blank_record(
                "materias", universidad_nombre=name,
                carrera_o_programa=programme.nombre,
                nombre_materia=subject["nombre"], anio_cursada=subject["anio"],
                turno=None, area_tematica=None, descripcion_breve=None,
                regimen=None, carga_horaria_semanal=None,
            ))

    data["facultades"] = [blank_record(
        "facultades", universidad_nombre=name, nombre_facultad=faculty,
        tipo_unidad=_tipo_unidad(faculty), sede=None,
    ) for faculty in sorted(faculties)]
    data["autoridades"] = [blank_record("autoridades", **row)
                           for row in personas.values()]
    data["redes_contacto"] = [blank_record(
        "redes_contacto", universidad_nombre=name,
        facultad_nombre=row["facultad_nombre"], canal=row["canal"],
        usuario_o_direccion=row["usuario_o_direccion"],
    ) for row in canales.values()]

    missing = [section for section, rows in data.items() if not rows]
    return {
        "universidad": name,
        "fuente_principal": universidad.sitio_web,
        "extraido_en": datetime.now(timezone.utc).isoformat(),
        "metodo": "HTML público; la carrera se reconoce por el título que "
                  "declara su encabezado; sin IA",
        "datos": data,
        "recursos_publicos": [],
        "detalle_programas": detail,
        "directorio_academico": {"personas": [], "roles_academicos": []},
        "control_calidad": {
            "secciones_vacias": missing,
            # Only a section that stayed empty needs a reason for it.
            "secciones_sin_fuente_publica": {
                section: reason for section, reason in RAZONES.items()
                if section in missing
            },
            "paginas_recorridas": descubiertas,
            "programas_descubiertos": len(programas),
            "programas_excluidos": excluded,
            "errores_descarga": errores or [],
            "nota": "Los valores ausentes permanecen nulos; no se inventan datos.",
        },
    }


# Why this reader leaves a section empty. It reads what every university
# publishes in the same shape; a section a university publishes in its own
# shape is left to an adapter written for that university.
RAZONES = {
    "sedes": "el lector general no lee el domicilio de cada sede",
    "aranceles": "el arancel se publica fuera de la página de la carrera",
    "turnos_anio": "no se publica un catálogo de horarios por año",
    "ofertas_ciclo": "no se publica el cupo ni la fecha de cada ciclo",
    "areas_tematicas": "el plan no agrupa sus materias por área",
    "autoridades": "ninguna página de carrera nombró a su director",
    "actividades": "no se publica un catálogo de prácticas",
    "redes_contacto": "ninguna página publicó una dirección de la universidad",
    "becas": "el lector general no lee el catálogo de becas",
    "servicios_estudiantiles": "el lector general no lee los servicios",
    "actividades_extracurriculares": "el lector general no lee las actividades",
    "alojamiento": "el lector general no lee el alojamiento",
    "programas_internacionales": "el lector general no lee los intercambios",
    "convenios_intercambio": "el lector general no lee los convenios",
}

_TIPOS_UNIDAD = (("facultad", "Facultad"), ("escuela", "Escuela"),
                 ("departamento", "Departamento"), ("instituto", "Departamento"),
                 ("centro", "Centro"))


def _tipo_unidad(nombre: str) -> str:
    key = comparison_key(nombre)
    for token, kind in _TIPOS_UNIDAD:
        if key.startswith(token):
            return kind
    # A unit named by its subject alone is a departamento at every national
    # university that names one that way.
    return "Departamento"


# An award is a name, not a paragraph and not a link.
_NO_ES_TITULO = re.compile(r"(?i)https?://|@|^\d+$|\.\s+\w")


def _titulo(value: str | None) -> str | None:
    """The award a page states under its own label.

    The value is not required to read like a degree. The page labelled it as
    the award, and a university names the award for the person rather than
    for the programme: the degree is "Ingeniería Industrial" and the award it
    gives is "Ingeniero/a Industrial".
    """
    text = clean_text(value)
    if not (4 <= len(text) <= 120) or len(text.split()) > 16:
        return None
    return None if _NO_ES_TITULO.search(text) else text


# --------------------------------------------------- the people and the post

# The post a university gives someone, and the kind of authority the schema
# files it under.
# Each post is anchored at a word boundary. Without it "Directora" holds
# "rector" inside it, and the director of a degree is filed as the rector of
# the university.
_CARGOS: tuple[tuple[str, str], ...] = (
    # Spanish doubles the r: a vicerrector is not a "vice" plus a "rector".
    (r"\bvice-?rrector[a]?\b|\brector[a]?\b|\bpresidente\b", "Institucional"),
    (r"\b(?:vice)?decan[oa]\b", "Institucional"),
    (r"\b(?:pro)?secretari[oa]\b|\badministrador[a]?\b", "Administrativo"),
    (r"\b(?:co)?director[a]?\b|\bcoordinador[a]?\b|\bjefe\b|"
     r"\btitular de c[áa]tedra\b", "Académico"),
)
_SEPARADOR_CARGO = re.compile(r"\s+[–—-]\s+|\s*\|\s*")
# A person's name: two to five words that each begin in capitals.
_UN_NOMBRE = re.compile(r"^(?:[A-ZÁÉÍÓÚÑÜ][\w'’.-]+(?:\s+(?:de|del|la|los|y)\s+)?\s*){2,5}$")


def cargo_de(texto: str) -> str | None:
    """The kind of authority a post belongs to, when it names a post."""
    key = comparison_key(texto)
    for pattern, kind in _CARGOS:
        if re.search(pattern, key):
            return kind
    return None


def leer_autoridades(html: str) -> list[dict[str, str]]:
    """Read the people a page names for a post, with the post they hold.

    A line only becomes a person when both halves of it read as one: a name
    on one side of the dash and a post on the other. A page prints many pairs
    of words around a dash and almost none of them are people.
    """
    soup = _soup(html)
    for element in soup(["nav", "footer", "header", "aside", "form", "select"]):
        element.decompose()
    _quitar_accesorios(soup)
    people: list[dict[str, str]] = []
    seen: set[str] = set()
    for line in _lineas(soup):
        if not (10 <= len(line) <= 140):
            continue
        parts = [clean_text(part) for part in _SEPARADOR_CARGO.split(line) if clean_text(part)]
        if len(parts) != 2:
            continue
        for name, post in (parts, parts[::-1]):
            if not _UN_NOMBRE.match(name) or cargo_de(name):
                continue
            kind = cargo_de(post)
            if not kind or len(post) > 90:
                continue
            key = comparison_key(f"{name}|{post}")
            if key in seen:
                continue
            seen.add(key)
            people.append({"nombre": name, "cargo": post, "tipo": kind})
            break
    return people


_UN_MAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
# An address a form or a tracker leaves behind, not one a person writes to.
_NO_ES_MAIL = re.compile(r"(?i)^(no-?reply|postmaster|webmaster|sentry|example|"
                         r"usuario|email|tu-?mail)@|\.(png|jpg|gif|js|css)$")


def leer_contactos(html: str, dominios: tuple[str, ...]) -> list[dict[str, str]]:
    """Read the mail addresses a programme page publishes for itself."""
    soup = _soup(html)
    for element in soup(["nav", "footer", "header", "aside", "form", "select"]):
        element.decompose()
    _quitar_accesorios(soup)
    found: list[dict[str, str]] = []
    seen: set[str] = set()
    for match in _UN_MAIL.finditer(soup.get_text(" ")):
        value = clean_text(match.group(0)).lower().rstrip(".,;")
        domain = value.split("@")[-1]
        if _NO_ES_MAIL.search(value) or value in seen:
            continue
        # Only an address of the university itself: a page names the mail of
        # a conference, a publisher and a supplier as readily as its own.
        if not any(domain == host or domain.endswith("." + host) for host in dominios):
            continue
        seen.add(value)
        found.append({"canal": "Email", "usuario_o_direccion": value})
    return found


_NIVELES_PUBLICADOS = (
    (r"posgrado|postgrado", "Posgrado"),
    (r"pregrado|tecnicatura|t[ée]cnic", "Pregrado"),
    (r"\bgrado\b", "Grado"),
)


def _nivel_publicado(value: str | None) -> str | None:
    """The level a page states under its own label, when it states one."""
    key = comparison_key(value)
    if not key or len(key) > 40:
        return None
    for pattern, level in _NIVELES_PUBLICADOS:
        if re.search(pattern, key):
            return level
    return None


def _sin_recortes(programas: list[Programa],
                  excluidos: list[dict[str, str]]) -> list[Programa]:
    """Drop the names a page published cut short.

    A site that writes the name of a career into the title of the window
    sometimes truncates it, so the same career arrives twice: once whole and
    once a few letters shorter. The whole one is kept.
    """
    keys = {comparison_key(programme.nombre) for programme in programas}
    kept: list[Programa] = []
    for programme in programas:
        key = comparison_key(programme.nombre)
        longer = next((other for other in keys
                       if other != key and other.startswith(key)
                       and len(other) - len(key) <= 3), None)
        if longer:
            excluidos.append({"programa": programme.nombre, "url": programme.url,
                              "motivo": "el nombre llega cortado; se conserva el entero"})
            continue
        kept.append(programme)
    return kept
