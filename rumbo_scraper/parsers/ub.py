"""Deterministic parsers for the public pages of Universidad de Belgrano.

Belgrano publishes the richest fact sheet of the sites read so far: every
programme page carries a table that states the degree it awards, the
intermediate one, the modality, the length, how many subjects it has, the shift
and its CONEAU accreditation. The plan is a PDF beside it.
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

UNIVERSITY = "Universidad de Belgrano"
SHORT_NAME = "UB"
BASE_URL = "https://www.ub.edu.ar"
DOMAIN = "ub.edu.ar"

# The three lists the university publishes, and the level each one gathers.
INDEXES: tuple[tuple[str, str], ...] = (
    ("/distribucion-carreras-de-grado", "Grado"),
    ("/distribucion-carreras-de-posgrados", "Posgrado"),
    ("/distribucion-carreras-distancia-fedev", "Grado"),
)
INDEX_URLS = tuple(f"{BASE_URL}{path}" for path, _ in INDEXES)

_PROGRAMME_PATH = re.compile(
    r"^/(facultad-[a-z0-9-]+|escuela-[a-z0-9-]+|departamento-[a-z0-9-]+)/([a-z0-9-]+)$"
)

# The fact sheet writes each label in capitals in the first column.
FACT_LABELS = {
    "titulo final": "titulo_final",
    "grado academico": "grado_academico",
    "titulo intermedio": "titulo_intermedio",
    "requisitos": "requisitos",
    "modalidad": "modalidad",
    "extension": "extension",
    "cantidad de materias": "cantidad_materias",
    "turno": "turno",
    "acreditacion de coneau": "coneau",
    "rm validez": "rm_validez",
}

POSTGRADUATE_KINDS = (
    ("doctorado", "Doctorado"),
    ("maestria", "Maestría"),
    ("magister", "Maestría"),
    ("especializacion", "Especialización"),
    ("diplomatura", "Diplomatura"),
)


@dataclass(frozen=True)
class ProgrammeRef:
    """A programme as one of the three lists publishes it."""

    name: str
    url: str
    level: str
    faculty: str


def faculty_name(slug: str) -> str:
    words = clean_text(slug.replace("-", " "))
    minor = {"de", "del", "la", "las", "los", "y", "e", "en", "para"}
    return " ".join(
        word if index and word in minor else word.capitalize()
        for index, word in enumerate(words.split())
    )


def discover_programmes(
    pages: dict[str, list[tuple[str, str]]]
) -> tuple[ProgrammeRef, ...]:
    """Read the programmes the three lists link, with the level of each list."""
    level_of = {f"{BASE_URL}{path}": level for path, level in INDEXES}
    refs: dict[str, ProgrammeRef] = {}
    for index_url, links in pages.items():
        level = level_of.get(index_url, "Grado")
        for href, label in links:
            path = urlparse(urljoin(BASE_URL, href or "")).path.rstrip("/")
            match = _PROGRAMME_PATH.match(path)
            name = clean_text(label)
            if not match or not name or len(name) > 90:
                continue
            url = f"{BASE_URL}{path}"
            refs.setdefault(
                url, ProgrammeRef(_titlecase(name), url, level,
                                  faculty_name(match.group(1)))
            )
    return tuple(sorted(refs.values(), key=lambda ref: comparison_key(ref.name)))


def _titlecase(name: str) -> str:
    """The lists write the names in capitals; restore the case they read in."""
    if not name.isupper():
        return name
    minor = {"de", "del", "la", "las", "los", "y", "e", "en", "para"}
    words = [word.lower() for word in clean_text(name).split()]
    return " ".join(
        word if index and word in minor else word.capitalize()
        for index, word in enumerate(words)
    )


def _soup(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style", "noscript"]):
        element.decompose()
    return soup


def parse_fact_sheet(html: str) -> dict[str, str]:
    """Read the table of facts the programme page publishes.

    A page without this table is not a programme: the same path shape is used
    by services such as the accounting clinic.
    """
    facts: dict[str, str] = {}
    for table in _soup(html).find_all("table"):
        for row in table.find_all("tr"):
            cells = [clean_text(cell.get_text(" ", strip=True))
                     for cell in row.find_all(["td", "th"])]
            if len(cells) < 2:
                continue
            key = FACT_LABELS.get(comparison_key(cells[0]))
            if key and cells[1]:
                facts.setdefault(key, cells[1])
    return facts


# The postgraduate pages carry no table and write the same facts in a
# sentence: "Duración: 2 años (4 cuatrimestres) Modalidad: Blended ...".
_INLINE_FACTS = (
    ("extension", r"Duraci[óo]n\s*:\s*(.{2,40}?)\s*(?=Modalidad|D[íi]as|$)"),
    ("modalidad", r"Modalidad\s*:\s*(.{2,50}?)\s*(?=Duraci[óo]n|D[íi]as|Tesis|$)"),
    ("coneau", r"Acreditaci[óo]n de CONEAU\s*(N[º°]?\s*[\d/\-]+)"),
    ("rm_validez", r"RM Validez\s*(N[º°]?\s*[\d/\-]+)"),
)


def parse_inline_facts(html: str) -> dict[str, str]:
    """Read the facts a page states in a sentence instead of a table."""
    text = clean_text(_soup(html).get_text(" ", strip=True))
    facts: dict[str, str] = {}
    for key, pattern in _INLINE_FACTS:
        match = re.search(pattern, text, re.I)
        if match:
            value = clean_text(match.group(1)).rstrip(".,;")
            if value:
                facts[key] = value
    return facts


def plan_document_url(html: str) -> str | None:
    """Find the document the page labels as the study plan."""
    for anchor in _soup(html).find_all("a", href=True):
        label = comparison_key(anchor.get_text(" ", strip=True))
        if "plan de estudio" in label and anchor["href"].lower().endswith(".pdf"):
            return urljoin(BASE_URL, anchor["href"])
    return None


_PLAN_YEAR = re.compile(
    r"^(PRIMER|SEGUNDO|TERCER|CUARTO|QUINTO|SEXTO|S[ÉE]PTIMO)\s+A[ÑN]O\b", re.I
)
_PLAN_TERM = re.compile(r"^(primer|segundo|tercer)\s+(semestre|cuatrimestre)", re.I)
_YEARS = {"primer": 1, "segundo": 2, "tercer": 3, "cuarto": 4,
          "quinto": 5, "sexto": 6, "septimo": 7}
_TERMS = {"semestre": "Semestral", "cuatrimestre": "Cuatrimestral"}
_BULLET = re.compile(r"^[•·\-•·]\s*")


def parse_plan_pdf(pdf_bytes: bytes, programme: str) -> list[dict[str, Any]]:
    """Read the plan document: a year in capitals, then its subjects."""
    from io import BytesIO

    from pypdf import PdfReader

    try:
        text = "\n".join(
            page.extract_text() or "" for page in PdfReader(BytesIO(pdf_bytes)).pages
        )
    except Exception:
        return []

    subjects: list[dict[str, Any]] = []
    seen: set[tuple[str, int | None]] = set()
    year: int | None = None
    regime: str | None = None
    for raw in text.splitlines():
        line = clean_text(raw)
        if not line:
            continue
        year_match = _PLAN_YEAR.match(line)
        if year_match:
            year = _YEARS.get(comparison_key(year_match.group(1)))
            continue
        term_match = _PLAN_TERM.match(line)
        if term_match:
            regime = _TERMS.get(comparison_key(term_match.group(2)))
            continue
        # Only a bulleted line is a subject; the rest is the cover and the
        # sentence that describes the programme.
        if year is None or not _BULLET.match(line):
            continue
        name = clean_text(_BULLET.sub("", line))
        if len(name) < 3:
            continue
        identity = (comparison_key(name), year)
        if identity in seen:
            continue
        seen.add(identity)
        subjects.append(blank_record(
            "materias", universidad_nombre=UNIVERSITY,
            carrera_o_programa=programme, nombre_materia=name,
            anio_cursada=year, turno=None, area_tematica=None,
            descripcion_breve=None, regimen=regime, carga_horaria_semanal=None,
        ))
    return subjects


def postgraduate_kind(name: str) -> str | None:
    key = comparison_key(name)
    for token, kind in POSTGRADUATE_KINDS:
        if re.search(rf"\b{token}", key):
            return kind
    return None


def duration_years(value: str | None) -> float | None:
    match = re.search(r"(\d+(?:[,.]\d+)?)\s*años?", value or "", re.I)
    return float(match.group(1).replace(",", ".")) if match else None


def duration_months(value: str | None) -> int | None:
    match = re.search(
        r"(\d+(?:[,.]\d+)?)\s*(años?|mes(?:es)?|cuatrimestres?|semestres?)",
        value or "", re.I,
    )
    if not match:
        return None
    factor = {"ano": 12, "anos": 12, "mes": 1, "meses": 1, "cuatrimestre": 4,
              "cuatrimestres": 4, "semestre": 6, "semestres": 6}
    return round(float(match.group(1).replace(",", ".")) * factor[comparison_key(match.group(2))])


def modality(value: str | None) -> str | None:
    key = comparison_key(value)
    if not key:
        return None
    in_person = "presencial" in key
    remote = any(word in key for word in ("distancia", "virtual", "online", "remoto"))
    if "semipresencial" in key or "hibrid" in key or (in_person and remote):
        return "Híbrida"
    if in_person:
        return "Presencial"
    if remote:
        return "Virtual"
    return None


def subject_count(value: str | None) -> int | None:
    match = re.search(r"\d+", value or "")
    return int(match.group()) if match else None


def build_dataset(
    programmes: tuple[ProgrammeRef, ...],
    programme_pages: dict[str, str],
    plan_documents: dict[str, bytes] | None = None,
    errors: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Assemble the Belgrano dataset from the pages and the plan documents."""
    data: dict[str, list[dict[str, Any]]] = {section: [] for section in SECTION_FIELDS}
    data["universidades"] = [blank_record(
        "universidades", nombre_oficial=UNIVERSITY, nombre_corto=SHORT_NAME,
        tipo_gestion="Privada", sitio_web=BASE_URL,
    )]

    plan_documents = plan_documents or {}
    details: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    resources: list[dict[str, Any]] = []
    for ref in programmes:
        html = programme_pages.get(ref.url, "")
        if not html:
            excluded.append({"nombre": ref.name, "url": ref.url,
                             "motivo": "la página no se pudo descargar"})
            continue
        facts = parse_fact_sheet(html) or parse_inline_facts(html)
        if not facts:
            # The same path shape is used by services, which state nothing
            # about a programme in either published form.
            excluded.append({"nombre": ref.name, "url": ref.url,
                             "motivo": "la página no publica datos de la carrera"})
            continue
        # The sheet states the academic level; the list it came from is the
        # fallback for the programmes that do not.
        published_level = clean_text(facts.get("grado_academico", ""))
        level = published_level.capitalize() if published_level else ref.level
        if comparison_key(level) not in ("grado", "posgrado", "pregrado"):
            level = ref.level
        document_url = plan_document_url(html)
        document = plan_documents.get(document_url or "", b"")
        subjects = parse_plan_pdf(document, ref.name) if document else []
        data["materias"].extend(subjects)
        detail = {
            "name": ref.name, "level": level, "url": ref.url, "faculty": ref.faculty,
            "plan_url": document_url, **facts,
        }
        details.append(detail)
        if document_url:
            resources.append({
                "entidad_tipo": "carrera" if level != "Posgrado" else "posgrado",
                "entidad_nombre": ref.name, "tipo_recurso": "documento",
                "titulo": f"Plan de estudios de {ref.name}",
                "url": document_url, "fuente_url": ref.url,
            })
        if level == "Posgrado":
            data["posgrados"].append(blank_record(
                "posgrados", universidad_nombre=UNIVERSITY, facultad_nombre=ref.faculty,
                nombre_programa=ref.name, tipo_posgrado=postgraduate_kind(ref.name),
                titulo_otorgado=facts.get("titulo_final"), sede=None,
                modalidad=modality(facts.get("modalidad")),
                duracion_meses=duration_months(facts.get("extension")),
                requiere_tesis_trabajo_final=None,
                requisito_titulo_previo=facts.get("requisitos"),
                cohorte_inicio=None, costo_total_programa=None, moneda=None,
                descripcion_breve=_description(html), url_oficial=ref.url,
            ))
            continue
        data["carreras"].append(blank_record(
            "carreras", universidad_nombre=UNIVERSITY, facultad_nombre=ref.faculty,
            nombre_carrera=ref.name, denominacion_canonica=ref.name, nivel=level,
            titulo_otorgado=facts.get("titulo_final"),
            tiene_titulo_intermedio=bool(facts.get("titulo_intermedio")) or None,
            duracion_anios=duration_years(facts.get("extension")),
            descripcion_breve=_description(html),
            cantidad_materias_total=subject_count(facts.get("cantidad_materias"))
            or (len(subjects) or None),
        ))
        data["ofertas"].append(blank_record(
            "ofertas", universidad_nombre=UNIVERSITY, facultad_nombre=ref.faculty,
            carrera_nombre=ref.name, sede=None,
            modalidad=modality(facts.get("modalidad")),
            regimen_ingreso=facts.get("requisitos"),
            # Belgrano is the only site that publishes its accreditation here.
            coneau_resolucion=facts.get("coneau"), coneau_vigencia_hasta=None,
            tiene_pasantias=None, tiene_bolsa_trabajo=None, url_oficial=ref.url,
        ))

    data["facultades"] = [blank_record(
        "facultades", universidad_nombre=UNIVERSITY, nombre_facultad=name,
        tipo_unidad="Facultad", sede=None,
    ) for name in sorted({detail["faculty"] for detail in details})]

    missing = [section for section, rows in data.items() if not rows]
    return {
        "universidad": UNIVERSITY,
        "fuente_principal": BASE_URL,
        "extraido_en": datetime.now(timezone.utc).isoformat(),
        "metodo": "HTML público y documentos de plan; sin IA",
        "datos": data,
        "recursos_publicos": resources,
        "detalle_programas": details,
        "directorio_academico": {"personas": [], "roles_academicos": []},
        "control_calidad": {
            "secciones_vacias": missing,
            "programas_descubiertos": len(programmes),
            "programas_excluidos": excluded,
            "errores_descarga": errors or [],
            "nota": "Los valores ausentes permanecen nulos; no se inventan datos.",
        },
    }


def _description(html: str) -> str | None:
    soup = _soup(html)
    for meta in soup.find_all("meta"):
        if (meta.get("name") or meta.get("property")) in ("description", "og:description"):
            value = clean_text(str(meta.get("content") or ""))
            if value:
                return value
    for paragraph in soup.find_all("p"):
        value = clean_text(paragraph.get_text(" ", strip=True))
        if len(value) >= 120:
            return value
    return None
