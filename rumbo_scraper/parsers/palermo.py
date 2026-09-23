"""Deterministic parsers for the public site of the Universidad de Palermo.

Palermo publishes a page per career under the section of its faculty, and a
page of its own for the plan. The plan page is the one worth reading: it
states the length, the modality, the degree and the intermediate degree, and
then lists the subjects under the year and the term that teach them.

The site writes the year split across two lines -- ``1`` and ``er año`` -- so
the lines are joined before they are read; a heading that arrives in halves is
still a heading.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from rumbo_scraper.contracts import SECTION_FIELDS, blank_record
from rumbo_scraper.normalizers.text import clean_text, comparison_key

UNIVERSITY = "Universidad de Palermo"
SHORT_NAME = "UP"
BASE_URL = "https://www.palermo.edu"
DOMAIN = "palermo.edu"

# The lists the university publishes, and the faculty each one gathers. There
# is no single catalogue: every faculty keeps its own index.
INDEXES: tuple[tuple[str, str], ...] = (
    (f"{BASE_URL}/derecho/", "Facultad de Derecho"),
    (f"{BASE_URL}/ingenieria/", "Facultad de Ingeniería"),
    (f"{BASE_URL}/negocios/indice-carreras-economicas.html",
     "Facultad de Ciencias Económicas"),
    (f"{BASE_URL}/cienciassociales/carreras.html", "Facultad de Ciencias Sociales"),
    (f"{BASE_URL}/dyc/inscripcion_carreras/", "Facultad de Diseño y Comunicación"),
)
INDEX_URLS = tuple(url for url, _ in INDEXES)

# A link is a career when its text opens with the kind of degree it is.
_CAREER_LABEL = re.compile(
    r"(?i)^(licenciatura|ingenier[íi]a|abogac[íi]a|contador|arquitectura|"
    r"dise[ñn]o|maestr[íi]a|especializaci[óo]n|doctorado|tecnicatura|"
    r"profesorado|mba)\b"
)
POSTGRADUATE_KINDS = (
    ("doctorado", "Doctorado"),
    ("maestria", "Maestría"),
    ("mba", "Maestría"),
    ("especializacion", "Especialización"),
    ("diplomatura", "Diplomatura"),
)

FACT_LABELS = {
    "duracion": "duracion",
    "modalidad": "modalidad",
    "titulo": "titulo",
    "titulo intermedio": "titulo_intermedio",
}


@dataclass(frozen=True)
class CareerRef:
    """A career as the index of its faculty publishes it."""

    name: str
    url: str
    faculty: str


def _soup(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style", "noscript"]):
        element.decompose()
    return soup


def decode(content: bytes, encoding: str | None) -> str:
    """The site serves some pages as iso-8859-1 and others as utf-8."""
    return content.decode(encoding or "utf-8", "replace")


def discover_careers(pages: dict[str, str]) -> tuple[CareerRef, ...]:
    """Read the careers the faculty indexes link, keeping the first faculty.

    A career taught both on campus and online is listed by two faculties under
    two addresses; it is one career, so the first index that names it wins.
    """
    faculty_of = dict(INDEXES)
    refs: dict[str, CareerRef] = {}
    for index_url, html in pages.items():
        faculty = faculty_of.get(index_url)
        if not faculty or not html:
            continue
        for anchor in _soup(html).find_all("a", href=True):
            name = clean_text(anchor.get_text(" ", strip=True))
            if not _CAREER_LABEL.match(name) or len(name) > 90:
                continue
            url = urljoin(index_url, clean_text(anchor["href"]))
            parsed = urlparse(url)
            if parsed.netloc.lower().lstrip("www.") != DOMAIN:
                continue
            url = f"https://{parsed.netloc}{parsed.path}"
            refs.setdefault(comparison_key(name), CareerRef(name, url, faculty))
    return tuple(refs.values())


def plan_url(html: str, page_url: str) -> str | None:
    """Find the page the career links as its plan of studies."""
    for anchor in _soup(html).find_all("a", href=True):
        if comparison_key(anchor.get_text(" ", strip=True)).startswith("plan de estudio"):
            url = urljoin(page_url, clean_text(anchor["href"]))
            if urlparse(url).netloc.lower().lstrip("www.") == DOMAIN:
                return url
    return None


def _lines(html: str) -> list[str]:
    soup = _soup(html)
    for element in soup(["nav", "footer", "header"]):
        element.decompose()
    return [clean_text(line) for line in soup.get_text("\n").split("\n") if clean_text(line)]


# The plan writes "1" on one line and "er año" on the next, so a heading is
# read from the pair and not from either half.
_ORDINAL_HALF = re.compile(r"^(er|do|ro|to|mo|vo|no|°|º)\s*(a[ñn]o|cuatrimestre)$", re.I)
_WHOLE_HEADING = re.compile(r"^(\d)\s*(?:er|do|ro|to|mo|vo|no|°|º)?\s*(a[ñn]o|cuatrimestre)$", re.I)
_TERMS = {"cuatrimestre": "Cuatrimestral"}


# A name the page wraps ends where the next line begins: "Teoría General del
# Acto Jurídico y de los" is the first half of "... y de los Contratos".
_UNFINISHED = re.compile(
    r"(?i)\b(de|del|la|las|el|los|un|una|y|e|en|para|por|con|a|al|su|sus|"
    r"sobre|entre)$"
)


def join_headings(lines: list[str]) -> list[str]:
    """Put back together what the page splits across two lines.

    Two things arrive in halves: the heading of a year, written as ``1`` and
    ``er año``, and the name of a subject that the column wrapped.
    """
    joined: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        following = lines[index + 1] if index + 1 < len(lines) else ""
        if re.fullmatch(r"\d", line) and _ORDINAL_HALF.match(following):
            joined.append(f"{line}{following}")
            index += 2
            continue
        if _UNFINISHED.search(line) and following and not _WHOLE_HEADING.match(following) \
                and len(following) < 60 and not _ORDINAL_HALF.match(following):
            joined.append(f"{line} {following}")
            index += 2
            continue
        joined.append(line)
        index += 1
    return joined


def parse_facts(html: str) -> dict[str, str]:
    """Read the facts the plan page states above the subjects."""
    lines = join_headings(_lines(html))
    facts: dict[str, str] = {}
    for position, line in enumerate(lines):
        key = FACT_LABELS.get(comparison_key(line).rstrip(":"))
        if not key or key in facts or position + 1 >= len(lines):
            continue
        value = lines[position + 1]
        if value and not value.endswith(":"):
            facts[key] = value
    return facts


# What the plan page says that is not the name of a subject.
_NOT_A_SUBJECT = re.compile(
    r"(?i)^(plan de estudio|duraci[óo]n|modalidad|t[íi]tulo|inscripci|m[áa]s info|"
    r"home|pr[áa]cticas profesionales|profesores|centro de|ocupaci[óo]n|"
    r"podr[áa]s|pod[ée]s|la carrera|el plan|contacto|consultas|becas|"
    r"universidad de palermo|facultad)"
)


def parse_plan_blocks(html: str, career: str) -> list[dict[str, Any]]:
    """Read a plan the page publishes as blocks of one year each.

    The markup says what the text cannot: the year is a box of its own class,
    the term is the paragraph that opens each half and every subject is a link
    inside the list. Where this shape is present it is the whole plan, and the
    descriptions printed below it are not part of it.
    """
    subjects: list[dict[str, Any]] = []
    seen: set[str] = set()
    for block in _soup(html).select("div.curso"):
        heading = block.select_one(".year")
        match = re.search(r"\d", clean_text(heading.get_text(" ", strip=True))) \
            if heading else None
        year = int(match.group()) if match else None
        for item in block.select("ul.bloque li a span, ul.bloque li a"):
            name = clean_text(item.get_text(" ", strip=True))
            if not name or len(name) < 4 or comparison_key(name) in seen:
                continue
            if _NOT_A_SUBJECT.match(name):
                continue
            seen.add(comparison_key(name))
            subjects.append(blank_record(
                "materias", universidad_nombre=UNIVERSITY,
                carrera_o_programa=career, nombre_materia=name,
                anio_cursada=year, turno=None, area_tematica=None,
                descripcion_breve=None, regimen=None, carga_horaria_semanal=None,
            ))
    return subjects


def parse_plan(html: str, career: str) -> list[dict[str, Any]]:
    """Read the subjects of a plan, under the year its heading announces.

    Nothing marks a subject apart from its place: it is a line between two
    headings. A line that is a sentence or a label of the page is left out,
    and a plan that publishes no heading publishes no year either.
    """
    blocks = parse_plan_blocks(html, career)
    if blocks:
        return blocks
    lines = join_headings(_lines(html))
    year: int | None = None
    regime: str | None = None
    started = False
    subjects: list[dict[str, Any]] = []
    # The page prints the plan again for every modality it is taught in, so a
    # subject is kept once and not once per repetition.
    seen: set[str] = set()
    for line in lines:
        heading = _WHOLE_HEADING.match(line)
        if heading:
            unit = comparison_key(heading.group(2))
            if unit.startswith("ano"):
                year, started = int(heading.group(1)), True
            else:
                regime = _TERMS.get(unit)
            continue
        if not started or _NOT_A_SUBJECT.match(line):
            continue
        # A sentence is not a subject: the plans write names, not prose.
        if len(line) < 4 or len(line) > 90 or line.count(" ") > 9 or "." in line[:-1]:
            continue
        if not re.search(r"[^\W\d_]{3}", line):
            continue
        identity = comparison_key(line)
        if identity in seen:
            continue
        seen.add(identity)
        subjects.append(blank_record(
            "materias", universidad_nombre=UNIVERSITY, carrera_o_programa=career,
            nombre_materia=line, anio_cursada=year, turno=None, area_tematica=None,
            descripcion_breve=None, regimen=regime, carga_horaria_semanal=None,
        ))
    return subjects


def duration_years(value: str | None) -> float | None:
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*a[ñn]os?", value or "", re.I)
    return float(match.group(1).replace(",", ".")) if match else None


def duration_months(value: str | None) -> int | None:
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*(a[ñn]os?|mes(?:es)?|cuatrimestres?)",
                      value or "", re.I)
    if not match:
        return None
    unit = comparison_key(match.group(2))
    factor = 12 if unit.startswith("ano") else (4 if unit.startswith("cuatri") else 1)
    return round(float(match.group(1).replace(",", ".")) * factor)


def modality(value: str | None) -> str | None:
    key = comparison_key(value)
    if not key:
        return None
    in_person = "presencial" in key and "semipresencial" not in key
    remote = any(word in key for word in ("distancia", "online", "virtual"))
    if "combinada" in key or "semipresencial" in key or "hibrid" in key \
            or (in_person and remote):
        return "Híbrida"
    if in_person:
        return "Presencial"
    if remote:
        return "Virtual"
    return None


def postgraduate_kind(name: str) -> str | None:
    key = comparison_key(name)
    for token, kind in POSTGRADUATE_KINDS:
        if re.search(rf"\b{token}", key):
            return kind
    return None


def build_dataset(
    careers: tuple[CareerRef, ...],
    plan_pages: dict[str, str],
    plan_of: dict[str, str] | None = None,
    errors: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Assemble the Palermo dataset from the plan page of every career."""
    data: dict[str, list[dict[str, Any]]] = {section: [] for section in SECTION_FIELDS}
    data["universidades"] = [blank_record(
        "universidades", nombre_oficial=UNIVERSITY, nombre_corto=SHORT_NAME,
        tipo_gestion="Privada", sitio_web=BASE_URL,
    )]

    plan_of = plan_of or {}
    details: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    faculties: set[str] = set()
    for ref in careers:
        plan = plan_of.get(ref.url)
        html = plan_pages.get(plan or "", "")
        if not html:
            excluded.append({"carrera": ref.name, "url": ref.url,
                             "motivo": "la carrera no publica una página de plan"})
            continue
        facts = parse_facts(html)
        subjects = parse_plan(html, ref.name)
        data["materias"].extend(subjects)
        faculties.add(ref.faculty)
        details.append({"nombre": ref.name, "facultad": ref.faculty,
                        "url": ref.url, "plan_url": plan,
                        "materias": len(subjects), **facts})
        kind = postgraduate_kind(ref.name)
        if kind:
            data["posgrados"].append(blank_record(
                "posgrados", universidad_nombre=UNIVERSITY, facultad_nombre=ref.faculty,
                nombre_programa=ref.name, tipo_posgrado=kind,
                titulo_otorgado=facts.get("titulo"), sede=None,
                modalidad=modality(facts.get("modalidad")),
                duracion_meses=duration_months(facts.get("duracion")),
                requiere_tesis_trabajo_final=None, requisito_titulo_previo=None,
                cohorte_inicio=None, costo_total_programa=None, moneda=None,
                descripcion_breve=None, url_oficial=ref.url,
            ))
            continue
        data["carreras"].append(blank_record(
            "carreras", universidad_nombre=UNIVERSITY, facultad_nombre=ref.faculty,
            nombre_carrera=ref.name, denominacion_canonica=ref.name, nivel="Grado",
            titulo_otorgado=facts.get("titulo"),
            tiene_titulo_intermedio=bool(facts.get("titulo_intermedio")) or None,
            duracion_anios=duration_years(facts.get("duracion")),
            descripcion_breve=None,
            cantidad_materias_total=len(subjects) or None,
        ))
        data["ofertas"].append(blank_record(
            "ofertas", universidad_nombre=UNIVERSITY, facultad_nombre=ref.faculty,
            carrera_nombre=ref.name, sede=None,
            modalidad=modality(facts.get("modalidad")), regimen_ingreso=None,
            coneau_resolucion=None, coneau_vigencia_hasta=None,
            tiene_pasantias=None, tiene_bolsa_trabajo=None, url_oficial=ref.url,
        ))

    data["facultades"] = [blank_record(
        "facultades", universidad_nombre=UNIVERSITY, nombre_facultad=faculty,
        tipo_unidad="Facultad", sede=None,
    ) for faculty in sorted(faculties)]

    missing = [section for section, rows in data.items() if not rows]
    return {
        "universidad": UNIVERSITY,
        "fuente_principal": BASE_URL,
        "extraido_en": datetime.now(timezone.utc).isoformat(),
        "metodo": "HTML público de la página de plan de cada carrera; sin IA",
        "datos": data,
        "recursos_publicos": [],
        "detalle_carreras": details,
        "directorio_academico": {"personas": [], "roles_academicos": []},
        "control_calidad": {
            "secciones_vacias": missing,
            "secciones_sin_fuente_publica": {
                "sedes": "el catálogo de carreras no dice en qué sede se dicta cada una",
                "aranceles": "el arancel no se publica junto a la carrera",
                "turnos_anio": "no se publica un catálogo de horarios",
                "ofertas_ciclo": "no se publica un ciclo de inscripción",
                "areas_tematicas": "el plan no agrupa las materias por área",
                "autoridades": "las autoridades se publican por facultad, fuera "
                               "del catálogo de carreras",
                "becas": "las becas se publican fuera del catálogo",
                "servicios_estudiantiles": "no hay catálogo de servicios",
                "actividades_extracurriculares": "no hay catálogo",
                "alojamiento": "no hay catálogo",
                "programas_internacionales": "no hay catálogo",
                "convenios_intercambio": "no hay catálogo",
                "redes_contacto": "no hay un directorio de contactos por facultad",
            },
            "carreras_descubiertas": len(careers),
            "carreras_excluidas": excluded,
            "errores_descarga": errors or [],
            "nota": "Los valores ausentes permanecen nulos; no se inventan datos.",
        },
    }
