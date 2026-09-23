"""Deterministic parsers for the public site of the UAI.

The Universidad Abierta Interamericana publishes one page per career under
``/facultades/<facultad>/<carrera>/``, and that page carries everything in a
form that can be read: a box of facts with the degree it awards, its
intermediate degree, its length and its modality; the campuses that teach it
with their address, telephone and shift; its authorities with their post and
mail; and, behind an iframe, the plan of studies as a table of subjects with
their year, their term, their code and their hours.

The iframe is the reason this adapter reaches further than the others: the
plan lives at ``nbapi.uai.edu.ar`` and is served as a table, not as a
scanned resolution.
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

UNIVERSITY = "Universidad Abierta Interamericana"
SHORT_NAME = "UAI"
BASE_URL = "https://uai.edu.ar"
DOMAIN = "uai.edu.ar"
SITEMAP_URL = f"{BASE_URL}/sitemap.xml"
PLAN_HOST = "https://nbapi.uai.edu.ar"

# A career is a page two levels below /facultades/; anything deeper is one of
# its tabs and anything shallower is the faculty itself.
_CAREER_PATH = re.compile(r"^/facultades/([^/]+)/([^/]+)/$")
# Two sections of the site sit beside the faculties without being one.
_NOT_A_FACULTY = {"publicaciones", "vicerrectoria-de-investigacion"}

# The page states the level of the career in a comment beside the plan, which
# is also where the code the plan endpoint expects is written.
_PLAN_COMMENT = re.compile(r"plan\s+(\S+)\s*(?:\n|\r|\s)*Carrera\s+de\s+(\w+)", re.I)
LEVELS = {"grado": "Grado", "posgrado": "Posgrado", "pregrado": "Pregrado"}

FACT_LABELS = {
    "titulo final": "titulo_final",
    "titulo intermedio": "titulo_intermedio",
    "duracion": "duracion",
    "modalidad": "modalidad",
}

POSTGRADUATE_KINDS = (
    ("doctorado", "Doctorado"),
    ("maestria", "Maestría"),
    ("magister", "Maestría"),
    ("especializacion", "Especialización"),
    ("especialista", "Especialización"),
    ("diplomatura", "Diplomatura"),
)


@dataclass(frozen=True)
class CareerRef:
    """A career as the sitemap publishes it."""

    faculty: str
    slug: str
    url: str


def _soup(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style", "noscript"]):
        element.decompose()
    return soup


def faculty_name(slug: str) -> str:
    """The name of a faculty out of the segment the sitemap writes."""
    words = clean_text(slug.replace("-", " "))
    minor = {"de", "del", "la", "las", "los", "y", "e", "en", "para"}
    return "Facultad de " + " ".join(
        word if index and word in minor else word.capitalize()
        for index, word in enumerate(words.split())
    )


def career_name(slug: str) -> str:
    words = clean_text(slug.replace("-", " "))
    minor = {"de", "del", "la", "las", "los", "y", "e", "en", "para", "con", "a"}
    return " ".join(
        word if index and word in minor else word.capitalize()
        for index, word in enumerate(words.split())
    )


def discover_careers(sitemap: str) -> tuple[CareerRef, ...]:
    """Read the careers the sitemap lists, one page each."""
    refs: dict[str, CareerRef] = {}
    for url in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", sitemap):
        parsed = urlparse(clean_text(url))
        if parsed.netloc.lower().lstrip("www.") != DOMAIN:
            continue
        match = _CAREER_PATH.match(parsed.path)
        if not match:
            continue
        faculty, slug = match.group(1), match.group(2)
        if comparison_key(faculty).replace(" ", "-") in _NOT_A_FACULTY:
            continue
        refs.setdefault(clean_text(url),
                        CareerRef(faculty_name(faculty), slug, clean_text(url)))
    return tuple(refs.values())


def parse_facts(html: str) -> dict[str, str]:
    """Read the box of facts the career page opens with.

    Every fact is written as ``<b>Label:</b> value`` inside the same box, so
    the label is the anchor and the value is what follows it.
    """
    facts: dict[str, str] = {}
    for label in _soup(html).select(".redbox b, .redbox strong"):
        key = FACT_LABELS.get(comparison_key(label.get_text(" ", strip=True)).rstrip(":"))
        if not key or key in facts:
            continue
        parent = label.parent
        value = clean_text(parent.get_text(" ", strip=True)) if parent else ""
        value = clean_text(value[len(clean_text(label.get_text(" ", strip=True))):])
        if value:
            facts[key] = value.lstrip(": ").strip()
    return facts


def parse_plan_reference(html: str) -> dict[str, str | None]:
    """Read the code of the career and the level its page declares.

    The site writes both in a comment beside the plan: the code the plan
    endpoint expects, and whether the page is a career of grado or of
    posgrado. Nothing else on the page states the level.
    """
    match = _PLAN_COMMENT.search(html)
    frame = _soup(html).select_one("#Estudio iframe")
    source = clean_text(frame.get("src")) if frame and frame.get("src") else None
    code = match.group(1) if match else None
    if not code and source:
        query = re.search(r"carrera=([^&]+)", source)
        code = query.group(1) if query else None
    level = LEVELS.get(comparison_key(match.group(2))) if match else None
    return {"codigo": code, "nivel": level, "plan_url": source}


def plan_index_url(code: str) -> str:
    return f"{PLAN_HOST}/tpl/planestudio?anioc=&carrera={code}&db=UAI"


def plan_detail_url(code: str, plan: str) -> str:
    return (f"{PLAN_HOST}/tpl/planestudiodetalle?carrera={code}&plan={plan}"
            f"&db=UAI&anio=2027&etapa=0")


def read_plan_codes(html: str) -> list[str]:
    """The plans the index offers for one career, newest first."""
    codes: list[str] = []
    for option in _soup(html).select("#planes option"):
        value = clean_text(option.get("value"))
        if value and value not in codes:
            codes.append(value)
    return sorted(codes, key=lambda value: -int(value) if value.isdigit() else 0)


# The plan writes the year and the term as headings over each block.
_PLAN_YEAR = re.compile(r"^(\d+)\s*(?:er|do|ro|to|mo|vo|no)?\s*a[ñn]o", re.I)
_PLAN_TERM = re.compile(r"materias del (primer|segundo|tercer) (cuatrimestre|semestre)", re.I)
_TERMS = {"cuatrimestre": "Cuatrimestral", "semestre": "Semestral"}
_COLUMN_LABELS = {"codigo", "asignatura", "correlativas", "carga", "materia",
                  "carga horaria", "teoricas", "practicas", "totales", "total",
                  "porcentaje", "titulo", "carga horaria total de carrera"}
# The plan opens with a summary of hours per year and closes with the degree
# it awards; neither is a subject.
_SUMMARY_LINE = re.compile(
    r"^(r\.m\.|nota n|uai\s*-|total|porcentaje|\d+%|,$|a[ñn]o\s*\d|"
    r"t[íi]tulo\b|.*-\s*plan\s*:)"
)


def parse_plan(html: str, career: str) -> list[dict[str, Any]]:
    """Read the subjects of a plan, with the year its block announces.

    The plan is not a table: it prints a heading for the year, another for the
    term and then, one line each, the code of the subject, its name, what it
    has as a correlative and its hours. A line of letters is a name and a line
    of digits is one of the numbers around it.
    """
    lines = [clean_text(line) for line in _soup(html).get_text("\n").split("\n")]
    lines = [line for line in lines if line]
    year: int | None = None
    regime: str | None = None
    subjects: list[dict[str, Any]] = []
    seen: set[tuple[str, int | None]] = set()
    started = False
    for line in lines:
        key = comparison_key(line)
        year_match = _PLAN_YEAR.match(key)
        if year_match:
            year, started = int(year_match.group(1)), True
            continue
        term_match = _PLAN_TERM.search(key)
        if term_match:
            regime = _TERMS.get(comparison_key(term_match.group(2)))
            continue
        if re.match(r"t[íi]tulo\b", key):
            # The plan closes with the degree it awards; what follows it is
            # the name of that degree and not another subject.
            started = False
            continue
        if not started or key in _COLUMN_LABELS or _SUMMARY_LINE.match(key):
            continue
        if not re.search(r"[^\W\d_]{3}", line) or len(line) < 4:
            continue
        name = clean_text(line).strip(" ,.;")
        identity = (comparison_key(name), year)
        if identity in seen:
            continue
        seen.add(identity)
        subjects.append(blank_record(
            "materias", universidad_nombre=UNIVERSITY, carrera_o_programa=career,
            nombre_materia=name, anio_cursada=year, turno=None, area_tematica=None,
            descripcion_breve=None, regimen=regime,
            # The plan states the total hours of the subject, not its weekly
            # load, so the weekly column stays empty.
            carga_horaria_semanal=None,
        ))
    return subjects


_ADDRESS = re.compile(r"^(.+?)\s*-\s*(CABA|Ciudad Aut[óo]noma de Buenos Aires|"
                      r"Rosario.*|.*Santa Fe.*)$", re.I)


def parse_campuses(html: str) -> list[dict[str, str]]:
    """Read the campuses the career page names, with what it says of each."""
    block = _soup(html).find(id="LocalizacionesYAranceles")
    if block is None:
        return []
    lines = [clean_text(line) for line in block.get_text("\n").split("\n")]
    lines = [line for line in lines if line and line != "•"]
    campuses: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in lines:
        if comparison_key(line) in ("localizaciones", ""):
            continue
        if line.endswith(":") and len(line) < 60:
            if current.get("nombre") and current.get("direccion"):
                campuses.append(current)
            current = {"nombre": clean_text(line).lstrip("• ").rstrip(":")}
            continue
        if _ADDRESS.match(line) and current.get("nombre") and "direccion" not in current:
            # Two campuses write "Cursada:" before the street; the label is
            # not part of the address.
            current["direccion"] = clean_text(re.sub(r"^\s*cursada\s*:\s*", "",
                                                     line, flags=re.I))
        elif line.lower().startswith("tel"):
            current["telefono"] = clean_text(line.split(":", 1)[-1])
        elif comparison_key(line).startswith("turno"):
            current["turno"] = clean_text(line.split(":", 1)[-1])
    if current.get("nombre") and current.get("direccion"):
        campuses.append(current)
    return campuses


_POST = re.compile(
    r"^(decan[oa]|vicedecan[oa]|director[a]?|secretari[oa]|coordinador[a]?)\b", re.I
)
_MAIL = re.compile(r"\S+@\S+")


def _person(cell: str) -> str:
    """The name in a cell that also carries the mail address beside it.

    The cross is the button that closes the panel with the person's CV; it
    renders inside the same cell as their name.
    """
    return clean_text(_MAIL.sub("", cell)).strip(" ,.;:×xX·")


def parse_authorities(html: str, faculty: str) -> list[dict[str, Any]]:
    """Read the authorities of the career out of the table that lists them.

    The table alternates a row of posts with a row of the people who hold
    them, one column per campus, and writes the mail address inside the same
    cell as the name.
    """
    block = _soup(html).find(id="Autoridades")
    if block is None:
        return []
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    pending: list[str] = []
    for table in block.find_all("table"):
        for row in table.find_all("tr"):
            cells = [clean_text(cell.get_text(" ", strip=True))
                     for cell in row.find_all(["td", "th"])]
            cells = [cell for cell in cells if cell and cell != "×"]
            if not cells:
                continue
            inline = [cell for cell in cells if _POST.match(cell) and ":" in cell]
            if inline:
                for cell in inline:
                    post, _, rest = cell.partition(":")
                    name = _person(rest)
                    if name:
                        rows.append((clean_text(post), name))
                pending = []
                continue
            if all(_POST.match(cell) for cell in cells):
                pending = [clean_text(cell) for cell in cells]
                continue
            if pending:
                for index, cell in enumerate(cells):
                    if index >= len(pending):
                        break
                    name = _person(cell)
                    if name and 6 <= len(name) <= 70:
                        rows.append((pending[index], name))
                pending = []
    records: list[dict[str, Any]] = []
    for post, name in rows:
        identity = (comparison_key(post), comparison_key(name))
        if identity in seen:
            continue
        seen.add(identity)
        records.append(blank_record(
            "autoridades", facultad_nombre=faculty, carrera=None, cargo=post,
            tipo="Académico", nombre_autoridad=name,
        ))
    return records


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
    remote = any(word in key for word in ("distancia", "virtual", "online"))
    if "semipresencial" in key or "hibrid" in key or (in_person and remote):
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
    pages: dict[str, str],
    plans: dict[str, list[dict[str, Any]]] | None = None,
    errors: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Assemble the UAI dataset from the page of every career."""
    data: dict[str, list[dict[str, Any]]] = {section: [] for section in SECTION_FIELDS}
    data["universidades"] = [blank_record(
        "universidades", nombre_oficial=UNIVERSITY, nombre_corto=SHORT_NAME,
        tipo_gestion="Privada", sitio_web=BASE_URL,
    )]

    plans = plans or {}
    details: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    campuses: dict[str, dict[str, str]] = {}
    authorities: list[dict[str, Any]] = []
    faculties: set[str] = set()
    for ref in careers:
        html = pages.get(ref.url, "")
        if not html:
            excluded.append({"carrera": ref.slug, "url": ref.url,
                             "motivo": "la página no se pudo descargar"})
            continue
        facts = parse_facts(html)
        reference = parse_plan_reference(html)
        level = reference["nivel"]
        if not level:
            # Without the level the page declares, the row would be filed by
            # guessing; the page is reported instead.
            excluded.append({"carrera": ref.slug, "url": ref.url,
                             "motivo": "la página no declara el nivel de la carrera"})
            continue
        name = career_name(ref.slug)
        faculties.add(ref.faculty)
        for campus in parse_campuses(html):
            campuses.setdefault(campus["nombre"], campus)
        authorities.extend(parse_authorities(html, ref.faculty))
        subjects = plans.get(ref.url, [])
        data["materias"].extend(subjects)
        details.append({
            "nombre": name, "facultad": ref.faculty, "nivel": level,
            "codigo": reference["codigo"], "url": ref.url,
            "materias": len(subjects), **facts,
        })

        if level == "Posgrado":
            data["posgrados"].append(blank_record(
                "posgrados", universidad_nombre=UNIVERSITY,
                facultad_nombre=ref.faculty, nombre_programa=name,
                tipo_posgrado=postgraduate_kind(name),
                titulo_otorgado=facts.get("titulo_final"), sede=None,
                modalidad=modality(facts.get("modalidad")),
                duracion_meses=duration_months(facts.get("duracion")),
                requiere_tesis_trabajo_final=None, requisito_titulo_previo=None,
                cohorte_inicio=None, costo_total_programa=None, moneda=None,
                descripcion_breve=None, url_oficial=ref.url,
            ))
            continue
        data["carreras"].append(blank_record(
            "carreras", universidad_nombre=UNIVERSITY, facultad_nombre=ref.faculty,
            nombre_carrera=name, denominacion_canonica=name, nivel=level,
            titulo_otorgado=facts.get("titulo_final"),
            tiene_titulo_intermedio=bool(facts.get("titulo_intermedio")) or None,
            duracion_anios=duration_years(facts.get("duracion")),
            descripcion_breve=None,
            cantidad_materias_total=len(subjects) or None,
        ))
        data["ofertas"].append(blank_record(
            "ofertas", universidad_nombre=UNIVERSITY, facultad_nombre=ref.faculty,
            carrera_nombre=name, sede=None,
            modalidad=modality(facts.get("modalidad")), regimen_ingreso=None,
            coneau_resolucion=None, coneau_vigencia_hasta=None,
            tiene_pasantias=None, tiene_bolsa_trabajo=None, url_oficial=ref.url,
        ))

    data["facultades"] = [blank_record(
        "facultades", universidad_nombre=UNIVERSITY, nombre_facultad=faculty,
        tipo_unidad="Facultad", sede=None,
    ) for faculty in sorted(faculties)]
    data["sedes"] = [blank_record(
        "sedes", universidad_nombre=UNIVERSITY, nombre_sede=campus["nombre"],
        localidad=None, calle=campus.get("direccion"), numero=None,
        tipo_sede="Campus",
    ) for campus in sorted(campuses.values(), key=lambda row: row["nombre"])]
    seen_authorities: set[tuple[str, str, str]] = set()
    for row in authorities:
        identity = (str(row["facultad_nombre"]), comparison_key(str(row["cargo"])),
                    comparison_key(str(row["nombre_autoridad"])))
        if identity in seen_authorities:
            continue
        seen_authorities.add(identity)
        data["autoridades"].append(row)

    missing = [section for section, rows in data.items() if not rows]
    return {
        "universidad": UNIVERSITY,
        "fuente_principal": BASE_URL,
        "extraido_en": datetime.now(timezone.utc).isoformat(),
        "metodo": "HTML público por carrera y el plan servido por nbapi; sin IA",
        "datos": data,
        "recursos_publicos": [],
        "detalle_carreras": details,
        "directorio_academico": {"personas": [], "roles_academicos": []},
        "control_calidad": {
            "secciones_vacias": missing,
            "secciones_sin_fuente_publica": {
                "aranceles": "el sitio no publica el arancel de cada carrera",
                "ofertas_ciclo": "no se publica un ciclo de inscripción",
                "turnos_anio": "el turno se publica por sede, no por año",
                "areas_tematicas": "el plan no agrupa las materias por área",
                "becas": "las becas se publican fuera del catálogo de carreras",
                "servicios_estudiantiles": "no hay catálogo de servicios",
                "actividades_extracurriculares": "no hay catálogo",
                "alojamiento": "no hay catálogo",
                "programas_internacionales": "no hay catálogo",
                "convenios_intercambio": "no hay catálogo",
            },
            "carreras_descubiertas": len(careers),
            "carreras_excluidas": excluded,
            "errores_descarga": errors or [],
            "nota": "Los valores ausentes permanecen nulos; no se inventan datos.",
        },
    }
