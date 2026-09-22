"""Deterministic parsers for the public pages of UADE.

The sitemap enumerates the whole site, and a programme is recognised by what
the university itself publishes about it: only a programme has a
`/plan-de-estudios` page. The pages are plain HTML.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any

from bs4 import BeautifulSoup

from rumbo_scraper.contracts import SECTION_FIELDS, blank_record
from rumbo_scraper.normalizers.text import clean_text, comparison_key

UNIVERSITY = "Universidad Argentina de la Empresa"
SHORT_NAME = "UADE"
BASE_URL = "https://www.uade.edu.ar"
SITEMAP_URL = f"{BASE_URL}/sitemap.xml"
DOMAIN = "uade.edu.ar"
PLAN_SUFFIX = "/plan-de-estudios"

_PROGRAMME_PATH = re.compile(
    r"^/(facultad-de-[a-z-]+|escuela-de-direccion-de-empresas)/([a-z0-9-]+)$"
)

# The name states what the programme is. UADE writes the kind first.
NAME_KINDS = (
    ("doctorado", "Posgrado", "Doctorado"),
    ("maestria", "Posgrado", "Maestría"),
    ("mba", "Posgrado", "Maestría"),
    ("especializacion", "Posgrado", "Especialización"),
    ("diplomatura", "Posgrado", "Diplomatura"),
    ("tecnicatura", "Pregrado", None),
    ("doble titulacion", "Grado", None),
    ("lic\\.", "Grado", None),
    ("ing\\.", "Grado", None),
    ("licenciatura", "Grado", None),
    ("ingenieria", "Grado", None),
    ("arquitectura", "Grado", None),
    ("abogacia", "Grado", None),
    ("contador", "Grado", None),
    ("profesorado", "Grado", None),
)

# The theme renders an icon as a text ligature after every subject name.
_ICON = re.compile(r"\s*(chevron_right|arrow_drop_down|expand_more|keyboard_arrow_\w+)\s*$")
_YEAR = re.compile(
    r"^(primer|segundo|tercer|cuarto|quinto|sexto|s[ée]ptimo)\s+a[ñn]o\b", re.I
)
_YEARS = {"primer": 1, "segundo": 2, "tercer": 3, "cuarto": 4,
          "quinto": 5, "sexto": 6, "septimo": 7}


@dataclass(frozen=True)
class ProgrammeRef:
    """A programme as the sitemap and the name publish it."""

    name: str
    url: str
    level: str
    kind: str | None
    faculty: str


def sitemap_paths(xml: str) -> list[str]:
    return sorted({
        clean_text(loc).replace(BASE_URL, "").rstrip("/")
        for loc in re.findall(r"<loc>([^<]+)</loc>", xml)
    })


def faculty_name(slug: str) -> str:
    words = clean_text(slug.replace("-", " "))
    minor = {"de", "del", "la", "las", "los", "y", "e"}
    return " ".join(
        word if index and word in minor else word.capitalize()
        for index, word in enumerate(words.split())
    )


def classify(name: str) -> tuple[str | None, str | None]:
    """Read the kind from the word the university writes first.

    A combined programme names both: "Lic. en Administración de Empresas + MBA"
    is a degree that continues into a master's, so the word that opens the name
    decides, not the order of this table.
    """
    key = comparison_key(name)
    best: tuple[int, str, str | None] | None = None
    for token, level, kind in NAME_KINDS:
        match = re.search(rf"\b{token}", key)
        if match and (best is None or match.start() < best[0]):
            best = (match.start(), level, kind)
    return (best[1], best[2]) if best else (None, None)


def discover_programmes(
    paths: list[str], titles: dict[str, str]
) -> tuple[tuple[ProgrammeRef, ...], list[dict[str, str]]]:
    """Enumerate the pages that publish a study plan.

    Having a plan is what the university publishes about a programme, so it
    separates a degree from a department or a landing page without needing a
    list kept by hand.
    """
    known = set(paths)
    refs: list[ProgrammeRef] = []
    excluded: list[dict[str, str]] = []
    for path in paths:
        match = _PROGRAMME_PATH.match(path)
        if not match or path + PLAN_SUFFIX not in known:
            continue
        url = f"{BASE_URL}{path}"
        name = clean_text(titles.get(path, ""))
        if not name:
            excluded.append({"nombre": path, "url": url,
                             "motivo": "la página no publica un título"})
            continue
        level, kind = classify(name)
        if level is None:
            excluded.append({"nombre": name, "url": url,
                             "motivo": "el nombre no declara el tipo de programa"})
            continue
        refs.append(ProgrammeRef(name, url, level, kind, faculty_name(match.group(1))))
    return tuple(sorted(refs, key=lambda ref: comparison_key(ref.name))), excluded


def _soup(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style", "noscript"]):
        element.decompose()
    return soup


def page_title(html: str) -> str | None:
    """The first heading is the name the university gives the programme."""
    heading = _soup(html).find("h1")
    return clean_text(heading.get_text(" ", strip=True)) if heading else None


def parse_facts(html: str) -> dict[str, str]:
    """Read the labelled facts the programme page states inline."""
    text = clean_text(_soup(html).get_text(" ", strip=True))
    values: dict[str, str] = {}
    for label, key in (("Duración", "duracion"),
                       ("Título intermedio", "titulo_intermedio")):
        match = re.search(
            rf"\b{label}\s*:?\s*(.{{2,70}}?)\s*"
            rf"(?=\s(?:Duración|Modalidad|Título|Quiero|Plan de estudios)\b|$)",
            text,
        )
        if match:
            value = clean_text(match.group(1)).rstrip(".,;")
            if value:
                values[key] = value
    # The modality is written as one word right after its label -- "Modalidad
    # blended", "Modalidad Online" -- and what follows is the sentence that
    # explains it, so only the word is read.
    modality_match = re.search(r"\bModalidad\s+([A-Za-zÁÉÍÓÚáéíóúñ]{4,20})", text)
    if modality_match:
        values["modalidad"] = clean_text(modality_match.group(1))
    return values


def parse_study_plan(html: str, programme: str) -> list[dict[str, Any]]:
    """Read the plan, published as a list per year."""
    soup = _soup(html)
    subjects: list[dict[str, Any]] = []
    seen: set[tuple[str, int | None]] = set()
    for group in soup.find_all(["ul", "ol"]):
        heading = group.find_previous(["h2", "h3", "h4", "strong", "p"])
        label = clean_text(heading.get_text(" ", strip=True)) if heading else ""
        year_match = _YEAR.match(label)
        if not year_match:
            continue
        year = _YEARS.get(comparison_key(year_match.group(1)))
        for item in group.find_all("li", recursive=False):
            name = _ICON.sub("", clean_text(item.get_text(" ", strip=True)))
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
                descripcion_breve=None, regimen=None, carga_horaria_semanal=None,
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
    remote = any(word in key for word in ("online", "virtual", "distancia", "remoto"))
    # UADE calls its mixed modality "blended".
    if any(word in key for word in ("semipresencial", "hibrid", "combinada", "blended")) \
            or (in_person and remote):
        return "Híbrida"
    if in_person:
        return "Presencial"
    if remote:
        return "Virtual"
    return None


def build_dataset(
    programmes: tuple[ProgrammeRef, ...],
    programme_pages: dict[str, str],
    plan_pages: dict[str, str] | None = None,
    excluded: list[dict[str, str]] | None = None,
    errors: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Assemble the UADE dataset from the pages that were downloaded."""
    data: dict[str, list[dict[str, Any]]] = {section: [] for section in SECTION_FIELDS}
    data["universidades"] = [blank_record(
        "universidades", nombre_oficial=UNIVERSITY, nombre_corto=SHORT_NAME,
        tipo_gestion="Privada", sitio_web=BASE_URL,
    )]
    data["facultades"] = [blank_record(
        "facultades", universidad_nombre=UNIVERSITY, nombre_facultad=name,
        tipo_unidad="Facultad", sede=None,
    ) for name in sorted({ref.faculty for ref in programmes})]

    plan_pages = plan_pages or {}
    details: list[dict[str, Any]] = []
    missing_pages = list(excluded or [])
    by_name: dict[str, list[dict[str, Any]]] = {}
    for ref in programmes:
        html = programme_pages.get(ref.url, "")
        if not html:
            missing_pages.append({"nombre": ref.name, "url": ref.url,
                                  "motivo": "la página no se pudo descargar"})
            continue
        facts = parse_facts(html)
        detail = {
            "name": ref.name, "level": ref.level, "kind": ref.kind, "url": ref.url,
            "faculty": ref.faculty, "duration": facts.get("duracion"),
            "modality": facts.get("modalidad"),
            "intermediate_degree": facts.get("titulo_intermedio"),
            "description": _description(html), "ref": ref,
        }
        details.append(detail)
        by_name.setdefault(comparison_key(ref.name), []).append(detail)

    for group in by_name.values():
        detail = max(group, key=_published_facts)
        ref = detail["ref"]
        subjects = parse_study_plan(plan_pages.get(ref.url + PLAN_SUFFIX, ""), ref.name)
        data["materias"].extend(subjects)
        if ref.level in ("Grado", "Pregrado"):
            data["carreras"].append(blank_record(
                "carreras", universidad_nombre=UNIVERSITY, facultad_nombre=ref.faculty,
                nombre_carrera=ref.name, denominacion_canonica=ref.name,
                nivel=ref.level,
                # The pages do not state the degree they award, only whether an
                # intermediate one exists.
                titulo_otorgado=None,
                tiene_titulo_intermedio=bool(detail["intermediate_degree"]) or None,
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
                titulo_otorgado=None, sede=None,
                modalidad=modality(detail["modality"]),
                duracion_meses=duration_months(detail["duration"]),
                requiere_tesis_trabajo_final=None, requisito_titulo_previo=None,
                cohorte_inicio=None, costo_total_programa=None, moneda=None,
                descripcion_breve=detail["description"], url_oficial=ref.url,
            ))

    merged = [
        {"nombre": group[0]["ref"].name,
         "urls": [item["ref"].url for item in group],
         "motivo": "la universidad lo publica en más de una sede o facultad"}
        for group in by_name.values() if len(group) > 1
    ]
    missing = [section for section, rows in data.items() if not rows]
    return {
        "universidad": UNIVERSITY,
        "fuente_principal": BASE_URL,
        "extraido_en": datetime.now(timezone.utc).isoformat(),
        "metodo": "HTML público enumerado por sitemap; sin IA",
        "datos": data,
        "recursos_publicos": [],
        "detalle_programas": [
            {key: value for key, value in detail.items() if key != "ref"}
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
        sum(1 for key in ("duration", "modality") if detail.get(key)),
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
