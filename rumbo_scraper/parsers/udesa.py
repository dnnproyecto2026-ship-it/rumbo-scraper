"""Deterministic parsers for Universidad de San Andrés public Next.js pages."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import re
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from rumbo_scraper.contracts import SECTION_FIELDS, blank_record
from rumbo_scraper.normalizers.text import clean_text, comparison_key


UNIVERSITY = "Universidad de San Andrés"
SHORT_NAME = "UdeSA"
BASE_URL = "https://udesa.edu.ar"
SOURCE_URL = f"{BASE_URL}/estudia-en-udesa"
CAMPUSES_URL = "https://exed.udesa.edu.ar/sedes/"
POSTGRADUATE_INDEX_URL = f"{BASE_URL}/posgrados"
FACULTY_DIRECTORY_URL = f"{BASE_URL}/cuerpo-docente"
# One entry per official page that publishes student-life content, with the
# contract section it feeds and the category the page itself represents. The
# category comes from the source, never from reading the text.
CONTENT_SOURCES: tuple[tuple[str, str, str], ...] = (
    ("becas", "/becas-doctorales", "Beca doctoral"),
    ("becas", "/becas-programas-internacionales", "Beca internacional"),
    ("servicios_estudiantiles", "/biblioteca", "Biblioteca"),
    ("servicios_estudiantiles", "/orientacion-al-alumno", "Orientación al alumno"),
    ("servicios_estudiantiles", "/desarrollo-profesional", "Desarrollo profesional"),
    ("servicios_estudiantiles", "/oficina-de-alumnos-de-grado", "Administración académica"),
    ("servicios_estudiantiles", "/oficina-de-alumnos-de-posgrado", "Administración académica"),
    ("servicios_estudiantiles", "/combi", "Transporte"),
    ("actividades_extracurriculares", "/deportes", "Deportes"),
    ("actividades_extracurriculares", "/student-life", "Vida estudiantil"),
    ("alojamiento", "/dormis", "Residencia"),
)
CONTENT_URLS = tuple(f"{BASE_URL}{path}" for _, path, _ in CONTENT_SOURCES)

AUTHORITY_URLS = (
    f"{BASE_URL}/conduccion-academica",
    f"{BASE_URL}/consejo-superior",
    f"{BASE_URL}/autoridades",
)

# The official index classifies each programme by the first word of its name.
# Anything outside this vocabulary -- an MBA, a "Master in ...", a
# "Profesorado Universitario" -- keeps a null type instead of being forced
# into an enum the source never claimed.
POSTGRADUATE_KINDS = {
    "diplomatura": "Diplomatura",
    "especializacion": "Especialización",
    "maestria": "Maestría",
    "doctorado": "Doctorado",
}

MONTHS_PER_UNIT = {"ano": 12, "anos": 12, "semestre": 6, "semestres": 6,
                   "cuatrimestre": 4, "cuatrimestres": 4, "mes": 1, "meses": 1}


@dataclass(frozen=True)
class CareerConfig:
    name: str
    faculty: str
    faculty_type: str
    url: str


# This catalogue mirrors the official undergraduate navigation. It is kept
# explicit so a redesign cannot silently turn unrelated links into careers.
CAREERS = (
    CareerConfig("Abogacía", "Derecho", "Departamento", "/departamento-de-derecho/abogacia"),
    CareerConfig("Licenciatura en Administración de Empresas", "Negocios", "Escuela", "/escuela-de-negocios/licenciatura-en-administracion-de-empresas"),
    CareerConfig("Licenciatura en Ciencia Política y Gobierno", "Ciencias Sociales", "Departamento", "/departamento-de-ciencias-sociales/licenciatura-en-ciencia-politica-y-gobierno"),
    CareerConfig("Licenciatura en Ciencias de la Educación", "Educación", "Escuela", "/escuela-de-educacion/licenciatura-en-ciencias-de-la-educacion"),
    CareerConfig("Licenciatura en Ciencias del Comportamiento", "Ciencias de la Vida y del Comportamiento", "Departamento", "/departamento-de-ciencias-de-la-vida-y-del-comportamiento/licenciatura-en-ciencias-del-comportamiento"),
    CareerConfig("Licenciatura en Comunicación", "Ciencias Sociales", "Departamento", "/departamento-de-ciencias-sociales/licenciatura-en-comunicacion"),
    CareerConfig("Licenciatura en Diseño", "Humanidades", "Departamento", "/departamento-de-humanidades/licenciatura-en-diseno"),
    CareerConfig("Licenciatura en Economía", "Economía", "Departamento", "/departamento-de-economia/licenciatura-en-economia"),
    CareerConfig("Licenciatura en Economía Empresarial", "Economía", "Departamento", "/departamento-de-economia/economia-empresarial"),
    CareerConfig("Licenciatura en Finanzas", "Negocios", "Escuela", "/escuela-de-negocios/licenciatura-en-finanzas"),
    CareerConfig("Licenciatura en Humanidades", "Humanidades", "Departamento", "/departamento-de-humanidades/licenciatura-en-humanidades"),
    CareerConfig("Ingeniería en Biotecnología", "Ingeniería", "Escuela", "/escuela-de-ingenieria/ingenieria-en-biotecnologia"),
    CareerConfig("Ingeniería en Inteligencia Artificial", "Ingeniería", "Escuela", "/escuela-de-ingenieria/ingenieria-en-inteligencia-artificial"),
    CareerConfig("Ingeniería Industrial", "Ingeniería", "Escuela", "/escuela-de-ingenieria/ingenieria-industrial"),
    CareerConfig("Ingeniería en Tecnologías Sustentables", "Ingeniería", "Escuela", "/escuela-de-ingenieria/ingenieria-en-tecnologias-sustentables"),
    CareerConfig("Licenciatura en Negocios Digitales", "Negocios", "Escuela", "/escuela-de-negocios/licenciatura-en-negocios-digitales"),
    CareerConfig("Profesorado en Educación Primaria", "Educación", "Escuela", "/escuela-de-educacion/profesorado-en-educacion-primaria"),
    CareerConfig("Licenciatura en Relaciones Internacionales", "Ciencias Sociales", "Departamento", "/departamento-de-ciencias-sociales/licenciatura-en-relaciones-internacionales"),
)


@dataclass(frozen=True)
class PostgraduateRef:
    """A programme as the official postgraduate index publishes it."""

    name: str
    url: str
    department: str | None


def _plain(value: Any) -> str | None:
    if value is None:
        return None
    text = clean_text(BeautifulSoup(str(value), "html.parser").get_text(" ", strip=True))
    return text or None


def _meta(page: dict[str, Any], key: str) -> str | None:
    for row in page.get("metatags") or []:
        if row.get("key") == key:
            return _plain(row.get("value"))
    return None


def _attendance(page: dict[str, Any]) -> dict[str, str]:
    return {
        comparison_key(row.get("label")): _plain(row.get("body")) or ""
        for row in page.get("attendance") or []
        if row.get("label")
    }


def _duration_years(value: str | None) -> float | None:
    match = re.search(r"(\d+(?:[,.]\d+)?)\s*años?", value or "", re.I)
    return float(match.group(1).replace(",", ".")) if match else None


def discover_plan_url(page: dict[str, Any], career_url: str) -> str | None:
    for card in page.get("navigationCards") or []:
        for item in card.get("undergraduatePage") or []:
            if comparison_key(item.get("undergraduatePageType")) == "plan de estudios":
                return urljoin(career_url, str(item.get("url") or ""))
    return None


def _entity_lists(payload: Any, key: str) -> list[dict[str, Any]]:
    """Collect every EntityList item stored under ``key``, at any depth.

    The index renders its programmes inside a numbered module, and the module
    order is presentation, not data. Walking the document keeps the discovery
    working when the page is rearranged.
    """
    found: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        for name, value in payload.items():
            if name == key and isinstance(value, dict):
                found.extend(item for item in value.get("items") or [] if isinstance(item, dict))
            else:
                found.extend(_entity_lists(value, key))
    elif isinstance(payload, list):
        for item in payload:
            found.extend(_entity_lists(item, key))
    return found


def discover_postgraduates(index_page: dict[str, Any]) -> tuple[PostgraduateRef, ...]:
    """Enumerate the programmes the official index classifies as postgraduate.

    Only ``Graduate`` entities count. Nothing is inferred from the URL shape,
    so a marketing page that happens to live under the same path is ignored.
    """
    refs: list[PostgraduateRef] = []
    seen: set[str] = set()
    for item in _entity_lists(index_page, "listDegreesModule29"):
        if item.get("__typename") != "Graduate":
            continue
        name = _plain(item.get("name"))
        url = str(item.get("url") or "").strip()
        if not name or not url:
            continue
        absolute = urljoin(BASE_URL, url)
        if absolute in seen:
            continue
        seen.add(absolute)
        departments = item.get("associatedDepartment") or []
        department = _plain(departments[0].get("name")) if departments else None
        refs.append(PostgraduateRef(name=name, url=absolute, department=department))
    return tuple(sorted(refs, key=lambda ref: comparison_key(ref.name)))


def postgraduate_kind(name: str) -> str | None:
    """Classify by the leading word the university itself publishes."""
    first = comparison_key(name).split(" ", 1)[0]
    return POSTGRADUATE_KINDS.get(first)


def duration_months(value: str | None) -> int | None:
    """Convert a published duration such as "1 año" or "3 cuatrimestres"."""
    match = re.search(
        r"(\d+(?:[,.]\d+)?)\s*(anos?|semestres?|cuatrimestres?|meses|mes)\b",
        comparison_key(value or ""),
    )
    if not match:
        return None
    amount = float(match.group(1).replace(",", "."))
    return round(amount * MONTHS_PER_UNIT[match.group(2)])


# The published cell is free text: "Presencial", "Online o Híbrida",
# "Flexible: presencial + online". The contract field is an enum, so only an
# unambiguous label is mapped and anything else stays null; the literal text is
# preserved in detalle_posgrados.
def postgraduate_modality(value: str | None) -> str | None:
    key = comparison_key(value)
    if not key:
        return None
    in_person = bool(re.search(r"presencial", key))
    remote = bool(re.search(r"online|virtual|a distancia|distancia", key))
    if re.search(r"hibrid", key) or (in_person and remote):
        return "Híbrida"
    if in_person:
        return "Presencial"
    if remote:
        return "Virtual"
    return None


# The same cell holds campuses, street addresses and even partner names
# ("Clarín / Riobamba / Artear / Radio Mitre"). Matching a token inside such a
# label would read a sponsor as a site, so the whole published label must be an
# official campus. Anything compound or unrecognised stays null and survives
# literally in detalle_posgrados.
CAMPUS_LABELS = {
    "campus victoria": "Campus Victoria",
    "victoria": "Campus Victoria",
    "sede nordelta": "Sede Nordelta",
    "nordelta": "Sede Nordelta",
    "sede callao": "Sede Callao",
    "callao": "Sede Callao",
    "sede riobamba": "Sede Riobamba",
    "riobamba": "Sede Riobamba",
}


def postgraduate_campus(value: str | None) -> str | None:
    return CAMPUS_LABELS.get(comparison_key(value))


def split_academic_unit(published: str | None) -> tuple[str, str] | None:
    """Split "Departamento de Economía" into its name and its kind."""
    text = clean_text(published)
    for kind in ("Escuela", "Departamento", "Centro"):
        prefix = f"{kind} de "
        if text.startswith(prefix):
            name = text[len(prefix):].strip()
            if name:
                return name, kind
    return None


def discover_graduate_plan_url(page: dict[str, Any], programme_url: str) -> str | None:
    for card in page.get("navigationCards") or []:
        for item in card.get("graduatePage") or []:
            # UdeSA fills one field or the other depending on the programme.
            label = item.get("graduatePageType") or item.get("undergraduatePageType")
            if comparison_key(label) == "plan de estudios":
                return urljoin(programme_url, str(item.get("url") or ""))
    return None


def parse_postgraduate_detail(
    ref: PostgraduateRef, page: dict[str, Any], final_url: str
) -> dict[str, Any]:
    """Read one programme page, keeping only what the page states."""
    if _plain(page.get("pageType")) != "Graduate":
        raise ValueError(f"{ref.name}: la página no es un posgrado ({page.get('pageType')!r}).")
    title = _plain(page.get("title")) or _plain(page.get("pageName"))
    if not title or comparison_key(title) != comparison_key(ref.name):
        raise ValueError(f"{ref.name}: la página publicó el título {title!r}.")
    attendance = _attendance(page)
    description = _plain((page.get("header") or {}).get("description"))
    if not description:
        description = _meta(page, "description") or _meta(page, "og:description")
    return {
        "name": ref.name,
        "department": ref.department,
        "url": final_url,
        # UdeSA labels this cell "Sede" or "Sedes" depending on the programme.
        "campus": postgraduate_campus(
            attendance.get("sede") or attendance.get("sedes")
        ),
        "campus_published": attendance.get("sede") or attendance.get("sedes") or None,
        "modality_published": attendance.get("modalidad") or None,
        "modality": postgraduate_modality(attendance.get("modalidad")),
        "duration_months": duration_months(attendance.get("duracion")),
        "start": attendance.get("inicio") or None,
        "description": description,
        "image_url": (page.get("header") or {}).get("src"),
        "plan_url": discover_graduate_plan_url(page, final_url),
    }


def parse_career_detail(
    config: CareerConfig, page: dict[str, Any], final_url: str
) -> dict[str, Any]:
    attendance = _attendance(page)
    description = _plain((page.get("header") or {}).get("description"))
    if not description:
        description = _meta(page, "description") or _meta(page, "og:description")
    title = _plain(page.get("title")) or _plain(page.get("pageName")) or config.name
    # Accept the configured name only when the official page is clearly the
    # same programme. This catches redirects to generic or error pages.
    if comparison_key(config.name).split(" en ")[-1] not in comparison_key(title):
        raise ValueError(f"La página de {config.name} redirigió a {title!r}.")
    return {
        "name": config.name,
        "faculty": config.faculty,
        "faculty_type": config.faculty_type,
        "url": final_url,
        "duration_years": _duration_years(attendance.get("duracion")),
        "campus": attendance.get("sede") or None,
        "modality": attendance.get("modalidad") or None,
        "start": attendance.get("inicio") or None,
        "description": description,
        "image_url": (page.get("header") or {}).get("src"),
        "plan_url": discover_plan_url(page, final_url),
    }


def parse_study_plan(
    page: dict[str, Any], career_name: str, source_url: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    syllabus = page.get("undergraduateSyllabus") or {}
    area_by_color = {
        str(row.get("color") or "").upper(): _plain(row.get("name"))
        for row in syllabus.get("references") or []
    }
    subjects: list[dict[str, Any]] = []
    seen: set[tuple[int, str]] = set()
    for semester in syllabus.get("table") or []:
        semester_name = _plain(semester.get("lateralHeading"))
        for table_row in semester.get("subTable") or []:
            for year_label, cell in table_row.items():
                if not isinstance(cell, dict):
                    continue
                name = _plain(cell.get("value"))
                year_match = re.search(r"\d+", str(year_label))
                if not name or not year_match:
                    continue
                year = int(year_match.group())
                identity = (year, comparison_key(name))
                if identity in seen:
                    continue
                seen.add(identity)
                subjects.append(blank_record(
                    "materias",
                    universidad_nombre=UNIVERSITY,
                    carrera_o_programa=career_name,
                    nombre_materia=name,
                    anio_cursada=year,
                    turno=None,
                    area_tematica=area_by_color.get(str(cell.get("color") or "").upper()),
                    descripcion_breve=None,
                    regimen="Semestral" if semester_name else None,
                    carga_horaria_semanal=None,
                ))
    resources: list[dict[str, Any]] = []
    for section in page.get("undergraduateSections") or []:
        for attachment_key in ("attachments3", "attachments6"):
            for item in section.get(attachment_key) or []:
                uri = item.get("src") or item.get("linkUri")
                if not uri:
                    continue
                resources.append({
                    "entidad_tipo": "carrera",
                    "entidad_nombre": career_name,
                    "tipo_recurso": "documento" if item.get("src") else "enlace",
                    "titulo": _plain(item.get("documentDescription") or item.get("linkTitle") or item.get("name")),
                    "url": urljoin(source_url, str(uri)),
                    "fuente_url": source_url,
                })
    return subjects, resources


# The postgraduate plan is prose, not the table the undergraduate pages use.
# Each list item is a subject, but many carry the lecturer, the meeting
# frequency or a footnote appended to the name. These rules cut only what the
# source marks explicitly, so nothing is guessed about where a name ends.
_ATTRIBUTION = re.compile(
    r"\s*[,\-–/;]\s*(?:a\s+cargo\s+de|prof(?:esor|esora)?\b|dr(?:a)?\.|lic\.|"
    r"mg\.|mag\.|ing\.|arq\.|phd\b|cpn\b).*$",
    re.I,
)
_TEACHER_SENTENCE = re.compile(r"\s*\.\s*(?:docentes?|profesores?|a\s+cargo\s+de)\s*:.*$", re.I)
_SCHEDULE = re.compile(
    r"\s*\.\s*(?:quincenal|mensual|semanal|bimestral|anual|intensiv[oa])\b.*$", re.I
)
_MEETINGS = re.compile(r"\s*\.\s*\d+\s*(?:encuentros?|clases?|horas?)\b.*$", re.I)
_PARENTHETICAL_TEACHER = re.compile(r"\s*\((?:coordinad|dictad|a\s+cargo)[^)]*\)", re.I)
# "Literaturas Comparadas / Luz Horne, PhD." puts the credential after the
# name instead of before it, so the separator alone does not reveal it.
_TRAILING_CREDENTIAL = re.compile(
    r"\s*[,\-–/;]\s*[^,;/]{2,60},\s*(?:phd|mba|m\.?a\.?|dr(?:a)?|lic|mg|mag)\.?\s*\.?\s*$",
    re.I,
)
# Some entries append the frequency without punctuation: "... en Educación
# Quincenal". A frequency word standing alone at the end is never part of a
# subject name.
_TRAILING_FREQUENCY = re.compile(
    r"\s+(?:quincenal|mensual|semanal|bimestral|intensiv[oa])\s*\.?\s*$", re.I
)
# Some entries append the course description to the name: "Seminario de
# Investigación I (marzo a mayo): Discusión temática. Su objetivo es que el
# estudiante...". A subject name is never two sentences, so only the first one
# is kept -- unless the period belongs to an abbreviation.
_ABBREVIATIONS = ("lic", "dr", "dra", "ing", "arq", "mg", "mag", "prof", "ph", "vs", "ej")
_SENTENCE_TAIL = re.compile(r"(?<=[a-záéíóúñ)\"])\.\s+\S.*$")
# Entries linking a file carry its weight: "Estructura Social Argentina (231.8 KB)".
_FILE_SIZE = re.compile(r"\s*\(\s*\d+(?:[.,]\d+)?\s*[KMG]B\s*\)\s*$", re.I)
_FOOTNOTE = re.compile(r"\s*\(\*+\)\s*$|\s*\*+\s*$")

# A plan stage can hold two kinds of list, and the paragraph above each one
# says which: "Se abordarán temáticas tales como:" introduces content, while
# "se trabajará en el desarrollo de habilidades de liderazgo directivo:"
# introduces competencies the graduate is expected to acquire. Competencies are
# not subjects, so the list they introduce is skipped whole.
_COMPETENCY_INTRO = re.compile(r"habilidades|competencias|perfil del egresad", re.I)

_STAGE_YEARS = {
    "primer": 1, "primero": 1, "1": 1, "1o": 1, "1er": 1,
    "segundo": 2, "2": 2, "2o": 2, "2do": 2,
    "tercer": 3, "tercero": 3, "3": 3, "3o": 3, "3er": 3,
    "cuarto": 4, "4": 4, "4o": 4, "4to": 4,
    "quinto": 5, "5": 5, "5o": 5, "5to": 5,
}
# "cuatrimestre" contains "trimestre", so the longer token is tested first.
_STAGE_REGIMES = (
    ("cuatrimestre", "Cuatrimestral"),
    ("trimestre", "Trimestral"),
    ("semestre", "Semestral"),
)


def clean_subject_name(raw: str) -> str | None:
    """Strip the lecturer and scheduling details the source appends to a name."""
    text = clean_text(raw)
    for pattern in (_PARENTHETICAL_TEACHER, _TEACHER_SENTENCE, _SCHEDULE,
                    _MEETINGS, _TRAILING_CREDENTIAL, _ATTRIBUTION,
                    _TRAILING_FREQUENCY, _FILE_SIZE):
        text = pattern.sub("", text)
    match = _SENTENCE_TAIL.search(text)
    if match:
        head = text[:match.start()]
        last_word = comparison_key(head.rsplit(" ", 1)[-1])
        if last_word not in _ABBREVIATIONS and len(head.strip()) >= 10:
            text = head
    text = _FOOTNOTE.sub("", text).strip().rstrip(".").strip()
    if len(text) < 3:
        return None
    # Subject names are published capitalised. A lowercase opening marks a
    # sentence of instructions -- "la entrega de la prepropuesta de tesis" --
    # not a subject.
    if not text[0].isupper():
        return None
    return text


def stage_year(label: str | None) -> int | None:
    """Read the year only from a stage that names one."""
    key = comparison_key(label)
    match = re.match(r"([a-z0-9]+)(?:er|o|do|to|ro|º|°)?\s+ano\b", key)
    return _STAGE_YEARS.get(match.group(1)) if match else None


def stage_regime(label: str | None) -> str | None:
    key = comparison_key(label)
    for token, regime in _STAGE_REGIMES:
        if token in key:
            return regime
    return None


def parse_postgraduate_plan(
    page: dict[str, Any], programme: str, source_url: str, excluded_names: frozenset[str] = frozenset()
) -> list[dict[str, Any]]:
    """Read the subjects a postgraduate plan lists, one row per list item."""
    subjects: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for stage in (page.get("graduateSyllabus") or {}).get("stages") or []:
        label = _plain(stage.get("label"))
        year, regime = stage_year(label), stage_regime(label)
        soup = BeautifulSoup(str(stage.get("body") or ""), "html.parser")
        items = []
        for group in soup.find_all(["ul", "ol"]):
            intro = group.find_previous(["p", "h2", "h3", "h4"])
            if intro and _COMPETENCY_INTRO.search(intro.get_text(" ", strip=True)):
                continue
            items.extend(group.find_all("li"))
        for item in items:
            # A few entries collapse a bullet list into a single item.
            for fragment in str(item.get_text(" ", strip=True)).split("•"):
                name = clean_subject_name(fragment)
                # A plan may cross-list another programme by name; that is a
                # pointer to a different degree, not a subject of this one.
                if not name or comparison_key(name) in excluded_names:
                    continue
                identity = (comparison_key(name), str(year))
                if identity in seen:
                    continue
                seen.add(identity)
                subjects.append(blank_record(
                    "materias", universidad_nombre=UNIVERSITY,
                    carrera_o_programa=programme, nombre_materia=name,
                    anio_cursada=year, turno=None, area_tematica=None,
                    descripcion_breve=None, regimen=regime,
                    carga_horaria_semanal=None,
                ))
    return subjects


# The body of a person card ends with the label of its link.
_LINK_LABEL = re.compile(r"\s*(?:ver\s+(?:perfil|m[áa]s)|conocelos?|contactar)\s*$", re.I)
# A position often names the unit it leads: "Director del Departamento de
# Ciencias Sociales". The unit is published inside the position, not beside it.
_POSITION_UNIT = re.compile(
    r"\b(?:de la|del|de)\s+((?:Departamento|Escuela|Centro)\s+de\s+[^,.;]+)$", re.I
)


def parse_content_blocks(page: dict[str, Any], source_url: str) -> list[dict[str, Any]]:
    """Read the titled blocks of a content page.

    The student-life pages are built from a small set of modules that all carry
    the same three fields: a label, an HTML body and an optional link. Reading
    that vocabulary works across pages instead of needing one parser per page.
    """
    blocks: list[dict[str, Any]] = []
    seen: set[str] = set()
    for section in page.get("sections") or []:
        candidates: list[dict[str, Any]] = [section]
        for key in ("cards", "cardIcon", "items"):
            entries = section.get(key)
            if isinstance(entries, list):
                candidates.extend(entry for entry in entries if isinstance(entry, dict))
        for entry in candidates:
            if entry.get("persons"):
                continue
            title = _plain(entry.get("label")) or _plain(entry.get("title"))
            body = _plain(entry.get("body")) or _plain(entry.get("summary"))
            link = entry.get("mediaLink") or {}
            url = str(link.get("linkUri") or "").strip()
            if not title or not body:
                continue
            key = comparison_key(title)
            if key in seen:
                continue
            seen.add(key)
            blocks.append({
                "titulo": title,
                "descripcion": body,
                "url": urljoin(source_url, url) if url else None,
                "fuente_url": source_url,
            })
    return blocks


# A heading is short and does not close a sentence; anything longer is prose.
HEADING_MAX_CHARS = 80


def _module_text(section: dict[str, Any]) -> tuple[str | None, str | None]:
    return _plain(section.get("label")) or _plain(section.get("title")), _plain(section.get("body"))


def parse_headed_blocks(page: dict[str, Any], source_url: str) -> list[dict[str, Any]]:
    """Read pages that publish a heading followed by its paragraphs.

    The residences page names each building in its own module and describes it
    in the ones that follow, so the blocks only exist as a sequence.
    """
    blocks: list[dict[str, Any]] = []
    heading: str | None = None
    paragraphs: list[str] = []

    def flush() -> None:
        if heading and paragraphs:
            blocks.append({
                "titulo": heading,
                "descripcion": clean_text(" ".join(paragraphs)),
                "url": None,
                "fuente_url": source_url,
            })

    for section in page.get("sections") or []:
        label, body = _module_text(section)
        if label and body:
            continue  # already covered by the label/body pairs
        text = label or body
        if not text:
            continue
        is_heading = len(text) <= HEADING_MAX_CHARS and not text.rstrip().endswith(".")
        if is_heading:
            flush()
            heading, paragraphs = text, []
        elif heading:
            paragraphs.append(text)
    flush()
    return blocks


def build_content_rows(
    section: str, category: str, blocks: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Turn published blocks into rows of the contract section they belong to.

    Only what the page states is kept. A scholarship's coverage, deadline or
    application process is not published as a labelled field, so those columns
    stay null rather than being read out of the prose.
    """
    rows: list[dict[str, Any]] = []
    for block in blocks:
        if section == "becas":
            rows.append(blank_record(
                "becas", universidad_nombre=UNIVERSITY, nombre_beca=block["titulo"],
                nivel="Posgrado" if "doctoral" in comparison_key(category) else None,
                tipo_beca=category, cobertura_descripcion=block["descripcion"],
                porcentaje_maximo=None, requisitos=None, proceso_postulacion=None,
                renovacion=None, fecha_cierre=None, url_postulacion=block["url"],
                contacto=None, fuente_url=block["fuente_url"],
            ))
        elif section == "servicios_estudiantiles":
            rows.append(blank_record(
                "servicios_estudiantiles", universidad_nombre=UNIVERSITY, sede=None,
                categoria=category, nombre_servicio=block["titulo"],
                descripcion=block["descripcion"], contacto=None, url=block["url"],
                fuente_url=block["fuente_url"],
            ))
        elif section == "actividades_extracurriculares":
            rows.append(blank_record(
                "actividades_extracurriculares", universidad_nombre=UNIVERSITY, sede=None,
                categoria=category, nombre_actividad=block["titulo"],
                descripcion=block["descripcion"], contacto=None, url=block["url"],
                fuente_url=block["fuente_url"],
            ))
        elif section == "alojamiento":
            rows.append(blank_record(
                "alojamiento", universidad_nombre=UNIVERSITY, sede=None,
                # The contract has no name column here, so the designation the
                # page publishes ("Jacarandá") is kept as the accommodation type.
                tipo_apoyo=category, tipo_alojamiento=block["titulo"],
                # The pages describe the buildings without stating who owns or
                # runs them, so ownership is not asserted.
                residencia_propia=None, descripcion=block["descripcion"],
                contacto=None, url=block["url"], fuente_url=block["fuente_url"],
            ))
    return rows


def _person_sections(page: dict[str, Any]) -> list[tuple[str | None, list[dict[str, Any]]]]:
    """Return every published group of people with the label above it."""
    groups: list[tuple[str | None, list[dict[str, Any]]]] = []
    for section in page.get("sections") or []:
        people = section.get("persons")
        if isinstance(people, list) and people:
            groups.append((_plain(section.get("label")), people))
    return groups


def parse_faculty_directory(
    page: dict[str, Any], source_url: str, unit_names: dict[str, str],
    programme_names: dict[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Read the published faculty list into people and their academic roles.

    Every professor is tagged with the units and programmes they teach in, so a
    person keeps one role per tag instead of being flattened into a single one.
    """
    people: list[dict[str, Any]] = []
    roles: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in (page.get("professors") or {}).get("items") or []:
        name = _plain(item.get("name"))
        if not name:
            continue
        key = comparison_key(name)
        if key in seen:
            continue
        seen.add(key)
        picture = item.get("professorPicture") or {}
        people.append({
            "universidad_nombre": UNIVERSITY,
            "nombre_completo": name,
            "email": None,
            "perfil_url": urljoin(source_url, str(item.get("url") or "")) or None,
            "foto_url": picture.get("src"),
            "formacion": None,
            "biografia": None,
            "fuente_url": source_url,
        })
        tags = [_plain(tag.get("name")) for tag in item.get("tags") or []]
        matched = False
        for tag in tags:
            if not tag:
                continue
            programme_faculty = programme_names.get(comparison_key(tag))
            if programme_faculty is not None:
                roles.append(_role(name, programme_faculty, tag, source_url))
                matched = True
        for tag in tags:
            unit = unit_names.get(comparison_key(tag or ""))
            if unit and not matched:
                roles.append(_role(name, unit, None, source_url))
                matched = True
        if not matched:
            roles.append(_role(name, None, None, source_url))
    return people, roles


def _role(
    name: str, faculty: str | None, career: str | None, source_url: str,
    cargo: str = "Profesor/a", is_authority: bool = False,
) -> dict[str, Any]:
    return {
        "nombre_completo": name, "facultad_nombre": faculty,
        "carrera_nombre": career, "materia_nombre": None, "cargo": cargo,
        "tipo_rol": "Académico", "es_autoridad": is_authority,
        "fuente_url": source_url,
    }


def parse_authorities(
    pages: dict[str, dict[str, Any]], unit_names: dict[str, str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Read the published authorities from the institutional pages.

    Two shapes are published: a module whose label reads "Name, Position" with
    the biography as its body, and a group of people whose body names either
    the unit they lead or the position they hold.
    """
    authorities: list[dict[str, Any]] = []
    people: list[dict[str, Any]] = []
    roles: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    # A person can hold more than one published position, and the same position
    # can appear on two pages. Positions are deduplicated per person, the
    # person only once.
    known_people: set[str] = set()

    def add(name: str, cargo: str, faculty: str | None, source_url: str,
            biography: str | None = None) -> None:
        cargo = clean_text(_LINK_LABEL.sub("", cargo))
        if faculty is None:
            match = _POSITION_UNIT.search(cargo)
            if match:
                faculty = unit_names.get(comparison_key(match.group(1)))
        identity = (comparison_key(name), comparison_key(cargo))
        if not name or not cargo or identity in seen:
            return
        seen.add(identity)
        if comparison_key(name) not in known_people:
            known_people.add(comparison_key(name))
            people.append({
                "universidad_nombre": UNIVERSITY, "nombre_completo": name,
                "email": None, "perfil_url": None, "foto_url": None,
                "formacion": None, "biografia": biography, "fuente_url": source_url,
            })
        authorities.append(blank_record(
            "autoridades", facultad_nombre=faculty, carrera=None, cargo=cargo,
            tipo="Académico", nombre_autoridad=name,
        ))
        roles.append(_role(name, faculty, None, source_url, cargo, True))

    for source_url, page in pages.items():
        for section in page.get("sections") or []:
            label = _plain(section.get("label"))
            # "Lucas S. Grosman, Rector" -- the module label carries both.
            if label and "," in label and section.get("body"):
                name, _, cargo = label.rpartition(",")
                add(clean_text(name), clean_text(cargo), None, source_url,
                    _plain(section.get("body")))
        for group_label, members in _person_sections(page):
            for member in members:
                name = _plain(member.get("name"))
                body = _plain(member.get("body")) or ""
                # The body is either the unit the person directs or the
                # position they hold; only a published unit becomes a faculty.
                # UdeSA writes "Departamento de Ingeniería" here while the
                # degree catalogue says "Escuela de Ingeniería", so an
                # unmatched unit leaves the faculty null instead of guessing.
                faculty = unit_names.get(comparison_key(body))
                group = comparison_key(group_label)
                if group == "directores":
                    cargo = "Director/a"
                elif group == "profesores emeritos":
                    cargo = "Profesor/a Emérito/a"
                elif faculty:
                    cargo = group_label or "Autoridad"
                else:
                    cargo = body or group_label or "Autoridad"
                add(str(name or ""), clean_text(cargo), faculty, source_url)
    return authorities, people, roles


def parse_campuses(html: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Extract addresses from UdeSA's official campuses page."""
    soup = BeautifulSoup(html, "html.parser")
    localities: dict[tuple[str, str], dict[str, Any]] = {}
    campuses: list[dict[str, Any]] = []
    for heading in soup.find_all("h2"):
        name = clean_text(heading.get_text(" ", strip=True))
        if name not in {"Campus Victoria", "Sede Callao", "Sede Nordelta", "Sede Riobamba"}:
            continue
        container = heading.parent
        text = clean_text(container.get_text(" ", strip=True))
        match = re.search(
            r"Dirección:\s*(.+?)\s+(\d+)\s+\(([^)]+)\)\s+(.+?)\s+Tel:", text, re.I
        )
        if not match:
            continue
        street, number, postal_code, location = match.groups()
        location_key = comparison_key(location)
        if "caba" in location_key:
            locality, province = "Ciudad Autónoma de Buenos Aires", "CABA"
        else:
            locality = clean_text(location.split(",", 1)[0])
            province = "Buenos Aires" if "bs. as" in location_key else None
        locality_ref = f"{locality} — {province}"
        localities[(locality, str(province))] = blank_record(
            "localidades", nombre_localidad=locality, provincia=province,
            codigo_postal=postal_code,
        )
        campuses.append(blank_record(
            "sedes", universidad_nombre=UNIVERSITY, nombre_sede=name,
            localidad=locality_ref, calle=street, numero=number,
            # The shared database enum has no generic "Sede" option. "Otro"
            # preserves the official label without misclassifying it as an
            # annex or a single-building institution.
            tipo_sede="Campus" if name.startswith("Campus") else "Otro",
        ))
    return list(localities.values()), campuses


def _campus_names(published_value: str | None) -> list[str]:
    """Normalize only campus names explicitly present in the published label."""
    key = comparison_key(published_value or "")
    names: list[str] = []
    if "campus victoria" in key:
        names.append("Campus Victoria")
    if "nordelta" in key:
        names.append("Sede Nordelta")
    if "caba" in key:
        # The official campuses page states that both CABA sites host these
        # two undergraduate programmes.
        names.extend(("Sede Callao", "Sede Riobamba"))
    return names


def build_dataset(
    landing_page: dict[str, Any],
    career_pages: dict[str, tuple[dict[str, Any], str]],
    plan_pages: dict[str, dict[str, Any]],
    campuses_html: str = "",
    errors: list[dict[str, str]] | None = None,
    postgraduate_refs: tuple[PostgraduateRef, ...] = (),
    postgraduate_pages: dict[str, tuple[dict[str, Any], str]] | None = None,
    postgraduate_plan_pages: dict[str, dict[str, Any]] | None = None,
    directory_page: dict[str, Any] | None = None,
    authority_pages: dict[str, dict[str, Any]] | None = None,
    content_pages: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    data: dict[str, list[dict[str, Any]]] = {section: [] for section in SECTION_FIELDS}
    data["universidades"] = [blank_record(
        "universidades", nombre_oficial=UNIVERSITY, nombre_corto=SHORT_NAME,
        tipo_gestion="Privada", sitio_web=BASE_URL,
    )]

    details: list[dict[str, Any]] = []
    resources: list[dict[str, Any]] = []
    landing_text = comparison_key(json.dumps(landing_page, ensure_ascii=False))
    campus_victoria_for_all = "campus victoria (todas las carreras)" in landing_text
    for config in CAREERS:
        configured_url = urljoin(BASE_URL, config.url)
        if configured_url not in career_pages:
            continue
        page, final_url = career_pages[configured_url]
        detail = parse_career_detail(config, page, final_url)
        details.append(detail)
        plan_url = detail["plan_url"]
        subjects: list[dict[str, Any]] = []
        if plan_url and plan_url in plan_pages:
            subjects, plan_resources = parse_study_plan(
                plan_pages[plan_url], config.name, plan_url
            )
            data["materias"].extend(subjects)
            resources.extend(plan_resources)
        faculty_name = f"{UNIVERSITY} — {config.faculty_type} de {config.faculty}"
        data["carreras"].append(blank_record(
            "carreras", universidad_nombre=UNIVERSITY,
            facultad_nombre=faculty_name, nombre_carrera=config.name,
            denominacion_canonica=config.name, nivel="Grado",
            titulo_otorgado=None, tiene_titulo_intermedio=None,
            duracion_anios=detail["duration_years"],
            descripcion_breve=detail["description"],
            cantidad_materias_total=len(subjects) or None,
        ))
        campus_names = _campus_names(detail["campus"])
        if not campus_names and campus_victoria_for_all:
            campus_names = ["Campus Victoria"]
        for campus_name in campus_names:
            data["ofertas"].append(blank_record(
                "ofertas", universidad_nombre=UNIVERSITY,
                facultad_nombre=faculty_name, carrera_nombre=config.name,
                sede=campus_name, modalidad=detail["modality"],
                regimen_ingreso=None, coneau_resolucion=None,
                coneau_vigencia_hasta=None, tiene_pasantias=None,
                tiene_bolsa_trabajo=None, url_oficial=detail["url"],
            ))
        if detail["image_url"]:
            resources.append({
                "entidad_tipo": "carrera", "entidad_nombre": config.name,
                "tipo_recurso": "imagen", "titulo": f"Imagen de {config.name}",
                "url": detail["image_url"], "fuente_url": detail["url"],
            })

    postgraduate_pages = postgraduate_pages or {}
    postgraduate_plan_pages = postgraduate_plan_pages or {}
    programme_names = frozenset(comparison_key(ref.name) for ref in postgraduate_refs)
    postgraduate_details: list[dict[str, Any]] = []
    postgraduate_units: set[tuple[str, str]] = set()
    excluded: list[dict[str, str]] = []
    for ref in postgraduate_refs:
        if ref.url not in postgraduate_pages:
            excluded.append({"nombre": ref.name, "url": ref.url,
                             "motivo": "la página no se pudo descargar"})
            continue
        page, final_url = postgraduate_pages[ref.url]
        try:
            detail = parse_postgraduate_detail(ref, page, final_url)
        except ValueError as error:
            excluded.append({"nombre": ref.name, "url": ref.url, "motivo": str(error)})
            continue
        unit = split_academic_unit(detail["department"])
        if unit:
            postgraduate_units.add(unit)
            detail["faculty_reference"] = f"{UNIVERSITY} — {unit[1]} de {unit[0]}"
        else:
            detail["faculty_reference"] = None
        postgraduate_details.append(detail)
        data["posgrados"].append(blank_record(
            "posgrados", universidad_nombre=UNIVERSITY,
            facultad_nombre=detail["faculty_reference"], nombre_programa=ref.name,
            tipo_posgrado=postgraduate_kind(ref.name),
            # The pages state neither the official degree nor the admission
            # requirements in a labelled field, and the project does not infer
            # them from prose. They stay null and surface in the audit.
            titulo_otorgado=None, sede=detail["campus"], modalidad=detail["modality"],
            duracion_meses=detail["duration_months"],
            requiere_tesis_trabajo_final=None, requisito_titulo_previo=None,
            cohorte_inicio=detail["start"], costo_total_programa=None, moneda=None,
            descripcion_breve=detail["description"], url_oficial=detail["url"],
        ))
        if detail["image_url"]:
            resources.append({
                "entidad_tipo": "posgrado", "entidad_nombre": ref.name,
                "tipo_recurso": "imagen", "titulo": f"Imagen de {ref.name}",
                "url": detail["image_url"], "fuente_url": detail["url"],
            })
        if detail["plan_url"]:
            plan_page = postgraduate_plan_pages.get(detail["plan_url"])
            if plan_page:
                data["materias"].extend(parse_postgraduate_plan(
                    plan_page, ref.name, detail["plan_url"], programme_names
                ))
            resources.append({
                "entidad_tipo": "posgrado", "entidad_nombre": ref.name,
                "tipo_recurso": "enlace", "titulo": f"Plan de estudios de {ref.name}",
                "url": detail["plan_url"], "fuente_url": detail["url"],
            })

    # Postgraduate programmes reach units the undergraduate catalogue does not
    # cover, such as the Departamento de Matemática y Ciencias.
    faculties = sorted(
        {(row.faculty, row.faculty_type) for row in CAREERS} | postgraduate_units
    )
    data["facultades"] = [blank_record(
        "facultades", universidad_nombre=UNIVERSITY,
        nombre_facultad=name, tipo_unidad=kind, sede=None,
    ) for name, kind in faculties]
    data["localidades"], data["sedes"] = parse_campuses(campuses_html)

    # Areas are aggregates of the plan classifications published by UdeSA.
    counts: dict[tuple[str, str], int] = {}
    for subject in data["materias"]:
        if subject["area_tematica"]:
            key = (str(subject["carrera_o_programa"]), str(subject["area_tematica"]))
            counts[key] = counts.get(key, 0) + 1
    faculty_by_career = {config.name: config.faculty for config in CAREERS}
    data["areas_tematicas"] = [blank_record(
        "areas_tematicas", universidad_nombre=UNIVERSITY,
        facultad_nombre=faculty_by_career[career], carrera_nombre=career,
        area_tematica=area, cantidad_materias=count,
    ) for (career, area), count in sorted(counts.items())]

    content_pages = content_pages or {}
    for section_name, path, category in CONTENT_SOURCES:
        page = content_pages.get(f"{BASE_URL}{path}")
        if not page:
            continue
        source_url = f"{BASE_URL}{path}"
        blocks = parse_content_blocks(page, source_url)
        blocks.extend(parse_headed_blocks(page, source_url))
        data[section_name].extend(build_content_rows(section_name, category, blocks))

    # Units and programmes are the vocabulary the directory tags people with.
    unit_names: dict[str, str] = {}
    for row in data["facultades"]:
        reference = f"{UNIVERSITY} — {row['tipo_unidad']} de {row['nombre_facultad']}"
        unit_names[comparison_key(f"{row['tipo_unidad']} de {row['nombre_facultad']}")] = reference
        unit_names[comparison_key(str(row["nombre_facultad"]))] = reference
    programme_faculties = {
        comparison_key(config.name): f"{UNIVERSITY} — {config.faculty_type} de {config.faculty}"
        for config in CAREERS
    }
    programme_faculties.update({
        comparison_key(str(row["nombre_programa"])): row["facultad_nombre"]
        for row in data["posgrados"]
    })

    people: list[dict[str, Any]] = []
    roles: list[dict[str, Any]] = []
    if directory_page:
        people, roles = parse_faculty_directory(
            directory_page, FACULTY_DIRECTORY_URL, unit_names, programme_faculties
        )
    if authority_pages:
        authorities, authority_people, authority_roles = parse_authorities(
            authority_pages, unit_names
        )
        data["autoridades"] = authorities
        known = {comparison_key(str(row["nombre_completo"])) for row in people}
        people.extend(
            row for row in authority_people
            if comparison_key(str(row["nombre_completo"])) not in known
        )
        roles.extend(authority_roles)

    missing = [section for section, rows in data.items() if not rows]
    return {
        "universidad": UNIVERSITY,
        "fuente_principal": SOURCE_URL,
        "extraido_en": datetime.now(timezone.utc).isoformat(),
        "metodo": "Playwright + JSON estructurado de Next.js; sin IA",
        "datos": data,
        "recursos_publicos": resources,
        "detalle_carreras": details,
        "detalle_posgrados": postgraduate_details,
        "directorio_academico": {"personas": people, "roles_academicos": roles},
        "control_calidad": {
            "secciones_vacias": missing,
            "posgrados_descubiertos": len(postgraduate_refs),
            "posgrados_excluidos": excluded,
            "errores_descarga": errors or [],
            "campos_inferidos": [],
            "nota": "Los valores ausentes permanecen nulos; no se inventan datos.",
        },
    }
