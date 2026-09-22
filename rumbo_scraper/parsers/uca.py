"""Deterministic parsers for the public pages of UCA.

The site renders on the client, so the pages are read through a browser. The
catalogue is reached the way the university links it: the faculties hub lists
the faculties, and each faculty page links its own programmes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from rumbo_scraper.contracts import SECTION_FIELDS, blank_record
from rumbo_scraper.normalizers.text import clean_text, comparison_key

UNIVERSITY = "Pontificia Universidad Católica Argentina"
SHORT_NAME = "UCA"
BASE_URL = "https://uca.edu.ar"
FACULTIES_URL = f"{BASE_URL}/es/facultades"
DOMAIN = "uca.edu.ar"

_FACULTY_PATH = re.compile(r"^/es/facultades/([a-z0-9-]+)/?$")
_PROGRAMME_PATH = re.compile(r"^/es/facultades/([a-z0-9-]+)/([a-z0-9-]+)/(.+)$")

# The segment between the faculty and the programme states what it is.
LEVEL_SEGMENTS = {
    "carrera-de-grado": ("Grado", None),
    "carreras-de-grado": ("Grado", None),
    "ciclo-de-licenciatura": ("Grado", None),
    "carrera-de-posgrado": ("Posgrado", None),
    "carreras-de-posgrado": ("Posgrado", None),
    "posgrado": ("Posgrado", None),
    "posgrados": ("Posgrado", None),
    "maestria": ("Posgrado", "Maestría"),
    "maestrias": ("Posgrado", "Maestría"),
    "doctorado": ("Posgrado", "Doctorado"),
    "doctorados": ("Posgrado", "Doctorado"),
    "especializacion": ("Posgrado", "Especialización"),
    "especializaciones": ("Posgrado", "Especialización"),
    "diplomatura": ("Posgrado", "Diplomatura"),
    "diplomaturas": ("Posgrado", "Diplomatura"),
}
# When the section does not state it, the name does. UCA writes the kind either
# first ("Licenciatura en Economía") or after the subject ("Inglés -
# Profesorado"), so the word is looked for anywhere in the name.
NAME_KINDS = (
    ("doctorado", "Posgrado", "Doctorado"),
    ("maestria", "Posgrado", "Maestría"),
    ("mba", "Posgrado", "Maestría"),
    ("especializacion", "Posgrado", "Especialización"),
    ("diplomatura", "Posgrado", "Diplomatura"),
    ("tecnicatura", "Pregrado", None),
    ("licenciatura", "Grado", None),
    ("ingenieria", "Grado", None),
    ("bioingenieria", "Grado", None),
    ("profesorado", "Grado", None),
    ("traductorado", "Grado", None),
    ("abogacia", "Grado", None),
    ("contador", "Grado", None),
    ("notariado", "Grado", None),
)


@dataclass(frozen=True)
class ProgrammeRef:
    """A programme as the faculty page links it."""

    name: str
    url: str
    level: str
    kind: str | None
    faculty: str


def faculty_name(slug: str) -> str:
    """"facultad-de-ciencias-sociales" is published as that slug only."""
    words = clean_text(slug.replace("-", " "))
    minor = {"de", "del", "la", "las", "los", "y", "e"}
    return " ".join(
        word if index and word in minor else word.capitalize()
        for index, word in enumerate(words.split())
    )


def discover_faculties(links: list[tuple[str, str]]) -> tuple[str, ...]:
    """Read the faculties the hub links."""
    urls: set[str] = set()
    for href, _label in links:
        path = urlparse(href or "").path
        if _FACULTY_PATH.match(path):
            urls.add(f"{BASE_URL}{path.rstrip('/')}")
    return tuple(sorted(urls))


def classify(name: str, section: str) -> tuple[str | None, str | None]:
    """Return the level and the kind, from the section or from the name."""
    level_kind = LEVEL_SEGMENTS.get(section)
    if level_kind:
        level, kind = level_kind
    else:
        level, kind = None, None
    key = comparison_key(name)
    for token, name_level, name_kind in NAME_KINDS:
        if re.search(rf"\b{token}", key):
            return level or name_level, kind or name_kind
    return level, kind


def discover_programmes(
    pages: dict[str, list[tuple[str, str]]]
) -> tuple[tuple[ProgrammeRef, ...], list[dict[str, str]]]:
    """Read the programmes each faculty page links."""
    refs: dict[str, ProgrammeRef] = {}
    excluded: list[dict[str, str]] = []
    for faculty_url, links in sorted(pages.items()):
        faculty_slug = urlparse(faculty_url).path.rstrip("/").rsplit("/", 1)[-1]
        for href, label in links:
            path = urlparse(href or "").path
            match = _PROGRAMME_PATH.match(path)
            name = clean_text(label)
            if not match or not name or len(name) > 90:
                continue
            if match.group(1) != faculty_slug:
                continue
            url = f"{BASE_URL}{path.rstrip('/')}"
            if url in refs:
                continue
            level, kind = classify(name, match.group(2))
            if level is None:
                excluded.append({"nombre": name, "url": url,
                                 "motivo": "ni la sección ni el nombre declaran el nivel"})
                continue
            refs[url] = ProgrammeRef(name, url, level, kind, faculty_name(faculty_slug))
    return tuple(sorted(refs.values(), key=lambda ref: comparison_key(ref.name))), excluded


def _soup(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style", "noscript"]):
        element.decompose()
    return soup


def parse_facts(html: str) -> dict[str, str]:
    """Read the labelled facts a programme page publishes in capitals."""
    text = clean_text(_soup(html).get_text(" ", strip=True))
    values: dict[str, str] = {}
    labels = ("TÍTULO", "DURACIÓN", "MODALIDAD", "SEDE", "ARTICULACIÓN",
              "TÍTULO INTERMEDIO", "REQUISITOS")
    others = "|".join(labels)
    for label in labels:
        # A value ends at the next label, at the "+" that opens the next
        # section, or at the end of the page. Without the "+" the last fact of
        # the strip -- usually the length -- was never read.
        match = re.search(
            rf"\b{label}\s*:\s*(.{{2,80}}?)\s*(?=\b(?:{others})\s*:|\s\+\s|$)", text
        )
        if match:
            value = clean_text(match.group(1)).rstrip(".,;")
            if value:
                values[comparison_key(label)] = value
    return values


_PLAN_YEAR = re.compile(
    r"^(PRIMER|SEGUNDO|TERCER|CUARTO|QUINTO|SEXTO|S[ÉE]PTIMO)\s+A[ÑN]O\b", re.I
)
_PLAN_TERM = re.compile(r"^(\d)\s*[º°]?\s*(semestre|cuatrimestre)", re.I)
_YEARS = {"primer": 1, "segundo": 2, "tercer": 3, "cuarto": 4,
          "quinto": 5, "sexto": 6, "septimo": 7}
_TERMS = {"semestre": "Semestral", "cuatrimestre": "Cuatrimestral"}


def parse_study_plan(html: str, programme: str) -> list[dict[str, Any]]:
    """Read the plan the page reveals, one paragraph per subject."""
    soup = _soup(html)
    anchor = soup.find(string=_PLAN_YEAR.search)
    if anchor is None:
        return []
    # Climb until the container holds every year the plan names, not just the
    # first: stopping at the first block with a few paragraphs cut the plan at
    # three subjects.
    total_years = len(soup.find_all(string=_PLAN_YEAR.search))
    container = anchor.parent
    for _ in range(8):
        if container is None or container.parent is None:
            break
        container = container.parent
        # The heading sits in its own paragraph, so a container that is still
        # inline text holds the year and nothing else.
        if container.name in ("p", "strong", "span", "b", "em"):
            continue
        if len(container.find_all(string=_PLAN_YEAR.search)) >= total_years:
            break
    if container is None:
        return []

    subjects: list[dict[str, Any]] = []
    seen: set[tuple[str, int | None]] = set()
    year: int | None = None
    regime: str | None = None
    # A paragraph holds a whole year, with its subjects separated by line
    # breaks, so reading it as one string would return a single long name.
    lines = [
        clean_text(line)
        for paragraph in container.find_all("p")
        for line in paragraph.get_text("\n").split("\n")
    ]
    for line in lines:
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
        # The plan also states the degrees it awards and its requirements;
        # those are labelled and are not subjects.
        if year is None or len(line) < 3 or line.isupper():
            continue
        if re.match(r"^(t[íi]tulo|requisito|observaci)", line, re.I):
            continue
        identity = (comparison_key(line), year)
        if identity in seen:
            continue
        seen.add(identity)
        subjects.append(blank_record(
            "materias", universidad_nombre=UNIVERSITY,
            carrera_o_programa=programme, nombre_materia=line,
            anio_cursada=year, turno=None, area_tematica=None,
            descripcion_breve=None, regimen=regime, carga_horaria_semanal=None,
        ))
    return subjects


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
    remote = any(word in key for word in ("virtual", "distancia", "online", "remoto"))
    if "semipresencial" in key or "hibrid" in key or (in_person and remote):
        return "Híbrida"
    if in_person:
        return "Presencial"
    if remote:
        return "Virtual"
    return None


def build_dataset(
    programmes: tuple[ProgrammeRef, ...],
    programme_pages: dict[str, str],
    excluded: list[dict[str, str]] | None = None,
    errors: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Assemble the UCA dataset from the pages that were rendered."""
    data: dict[str, list[dict[str, Any]]] = {section: [] for section in SECTION_FIELDS}
    data["universidades"] = [blank_record(
        "universidades", nombre_oficial=UNIVERSITY, nombre_corto=SHORT_NAME,
        tipo_gestion="Privada", sitio_web=BASE_URL,
    )]
    faculties = sorted({ref.faculty for ref in programmes})
    data["facultades"] = [blank_record(
        "facultades", universidad_nombre=UNIVERSITY, nombre_facultad=name,
        tipo_unidad="Facultad", sede=None,
    ) for name in faculties]

    details: list[dict[str, Any]] = []
    missing_pages = list(excluded or [])
    by_name: dict[str, list[dict[str, Any]]] = {}
    for ref in programmes:
        html = programme_pages.get(ref.url, "")
        if not html:
            missing_pages.append({"nombre": ref.name, "url": ref.url,
                                  "motivo": "la página no se pudo renderizar"})
            continue
        facts = parse_facts(html)
        detail = {
            "name": ref.name, "level": ref.level, "kind": ref.kind, "url": ref.url,
            "faculty": ref.faculty, "awarded_degree": facts.get("titulo"),
            "duration": facts.get("duracion"), "modality": facts.get("modalidad"),
            "published_campus": facts.get("sede"),
            "description": _description(html), "ref": ref, "html": html,
        }
        details.append(detail)
        by_name.setdefault(comparison_key(ref.name), []).append(detail)

    for group in by_name.values():
        detail = max(group, key=_published_facts)
        ref = detail["ref"]
        subjects = parse_study_plan(detail["html"], ref.name)
        data["materias"].extend(subjects)
        # A tecnicatura is a career too; the contract keeps its level.
        if ref.level in ("Grado", "Pregrado"):
            data["carreras"].append(blank_record(
                "carreras", universidad_nombre=UNIVERSITY, facultad_nombre=ref.faculty,
                nombre_carrera=ref.name, denominacion_canonica=ref.name,
                nivel=ref.level,
                titulo_otorgado=detail["awarded_degree"], tiene_titulo_intermedio=None,
                duracion_anios=duration_years(detail["duration"]),
                descripcion_breve=detail["description"],
                cantidad_materias_total=len(subjects) or None,
            ))
            data["ofertas"].append(blank_record(
                "ofertas", universidad_nombre=UNIVERSITY, facultad_nombre=ref.faculty,
                carrera_nombre=ref.name, sede=None,
                modalidad=modality(detail["modality"]), regimen_ingreso=None,
                coneau_resolucion=None, coneau_vigencia_hasta=None,
                tiene_pasantias=None, tiene_bolsa_trabajo=None, url_oficial=ref.url,
            ))
        else:
            data["posgrados"].append(blank_record(
                "posgrados", universidad_nombre=UNIVERSITY, facultad_nombre=ref.faculty,
                nombre_programa=ref.name, tipo_posgrado=ref.kind,
                titulo_otorgado=detail["awarded_degree"], sede=None,
                modalidad=modality(detail["modality"]),
                duracion_meses=duration_months(detail["duration"]),
                requiere_tesis_trabajo_final=None, requisito_titulo_previo=None,
                cohorte_inicio=None, costo_total_programa=None, moneda=None,
                descripcion_breve=detail["description"], url_oficial=ref.url,
            ))

    merged = [
        {"nombre": group[0]["ref"].name,
         "urls": [item["ref"].url for item in group],
         "motivo": "la universidad lo publica en más de una facultad o sección"}
        for group in by_name.values() if len(group) > 1
    ]
    missing = [section for section, rows in data.items() if not rows]
    return {
        "universidad": UNIVERSITY,
        "fuente_principal": BASE_URL,
        "extraido_en": datetime.now(timezone.utc).isoformat(),
        "metodo": "Navegador sobre páginas públicas; sin IA",
        "datos": data,
        "recursos_publicos": [],
        "detalle_programas": [
            {key: value for key, value in detail.items() if key not in ("ref", "html")}
            for detail in details
        ],
        "directorio_academico": {"personas": [], "roles_academicos": []},
        "control_calidad": {
            "secciones_vacias": missing,
            "programas_descubiertos": len(programmes),
            "programas_excluidos": missing_pages,
            "programas_unificados": merged,
            "errores_descarga": errors or [],
            "nota": "Los valores ausentes permanecen nulos; no se inventan datos.",
        },
    }


def _published_facts(detail: dict[str, Any]) -> tuple[int, int]:
    return (
        sum(1 for key in ("awarded_degree", "duration", "modality") if detail.get(key)),
        1 if detail.get("description") else 0,
    )


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
