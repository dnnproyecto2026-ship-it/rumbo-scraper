"""Deterministic parsers for the public pages and API of Universidad Austral.

The site is WordPress and exposes its REST API, which publishes the catalogue
as structured data: every programme carries the taxonomy that says what kind of
degree it is, which campus it belongs to and which academic area runs it. The
pages are only read for the facts the API does not carry.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from rumbo_scraper.contracts import SECTION_FIELDS, blank_record
from rumbo_scraper.normalizers.text import clean_text, comparison_key

UNIVERSITY = "Universidad Austral"
SHORT_NAME = "Austral"
BASE_URL = "https://www.austral.edu.ar"
API_URL = f"{BASE_URL}/wp-json/wp/v2"
DOMAIN = "austral.edu.ar"

# The taxonomy the university keeps for its own catalogue. Only the kinds the
# contract models are loaded; "Programas" gathers short executive courses that
# are neither a degree nor a postgraduate one.
DEGREE_KIND = "Carrera de grado"
POSTGRADUATE_KINDS = ("Maestría", "Doctorado", "Especialización", "Diplomatura")

ATTENDANCE_LABELS = ("Inicio", "Duración", "Modalidad", "Sede")


@dataclass(frozen=True)
class ProgrammeRef:
    """A programme as the catalogue publishes it."""

    name: str
    url: str
    level: str
    kind: str | None
    area: str | None
    campus: str | None


def _plain(value: Any) -> str | None:
    if value is None:
        return None
    text = clean_text(BeautifulSoup(str(value), "html.parser").get_text(" ", strip=True))
    return text or None


def discover_programmes(
    products: list[dict[str, Any]],
    kinds: dict[int, str],
    areas: dict[int, str],
    campuses: dict[int, str],
) -> tuple[tuple[ProgrammeRef, ...], list[dict[str, str]]]:
    """Split the catalogue into the programmes the contract models.

    Nothing is inferred from the name: the kind comes from the taxonomy the
    university assigns to each entry.
    """
    refs: list[ProgrammeRef] = []
    excluded: list[dict[str, str]] = []
    seen: set[str] = set()
    for product in products:
        name = _plain((product.get("title") or {}).get("rendered"))
        url = clean_text(str(product.get("link") or ""))
        if not name or not url or url in seen:
            continue
        seen.add(url)
        published = [kinds.get(term) for term in product.get("tipo-de-producto") or []]
        kind = next((value for value in published if value), None)
        area = next((areas.get(term) for term in product.get("areas-tax") or []), None)
        campus = next((campuses.get(term) for term in product.get("sedes") or []), None)
        if kind == DEGREE_KIND:
            level = "Grado"
            kind = None
        elif kind in POSTGRADUATE_KINDS:
            level = "Posgrado"
        else:
            excluded.append({"nombre": name, "url": url,
                             "motivo": f"el catálogo lo clasifica como {kind or 'sin tipo'}"})
            continue
        refs.append(ProgrammeRef(name, url, level, kind, area, _campus_name(campus)))
    return tuple(sorted(refs, key=lambda ref: comparison_key(ref.name))), excluded


def _campus_name(published: str | None) -> str | None:
    """"SEDE PILAR" is how the taxonomy writes it; keep the readable form."""
    text = clean_text(published)
    if not text:
        return None
    match = re.fullmatch(r"SEDE\s+(.+)", text, re.I)
    if not match:
        return text
    # Title case the words but leave a short acronym alone: CABA is not Caba.
    words = " ".join(
        word if len(word) <= 4 and word.isupper() else word.title()
        for word in match.group(1).split()
    )
    return f"Sede {words}"


def _soup(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style", "noscript"]):
        element.decompose()
    return soup


def parse_attendance(html: str) -> dict[str, str]:
    """Read the strip of labelled facts a programme page publishes."""
    text = clean_text(_soup(html).get_text(" ", strip=True))
    values: dict[str, str] = {}
    others = "|".join(ATTENDANCE_LABELS)
    for label in ATTENDANCE_LABELS:
        match = re.search(
            rf"\b{label}\s*:\s*(.{{1,60}}?)\s*(?=\b(?:{others})\s*:|$)", text
        )
        if match:
            value = clean_text(match.group(1)).rstrip(".,;")
            if value:
                values[comparison_key(label)] = value
    return values


def plan_document_url(html: str) -> str | None:
    """Find the download the page labels as the study plan."""
    for anchor in _soup(html).find_all("a", href=True):
        if "jet_download" not in anchor["href"]:
            continue
        label = comparison_key(anchor.get_text(" ", strip=True))
        if "plan de estudio" in label:
            return urljoin(BASE_URL, anchor["href"])
    return None


def duration_years(value: str | None) -> float | None:
    match = re.search(r"(\d+(?:[,.]\d+)?)\s*años?", value or "", re.I)
    return float(match.group(1).replace(",", ".")) if match else None


def duration_months(value: str | None) -> int | None:
    match = re.search(
        r"(\d+(?:[,.]\d+)?)\s*(años?|meses|cuatrimestres?|semestres?)", value or "", re.I
    )
    if not match:
        return None
    unit = comparison_key(match.group(2))
    factor = {"ano": 12, "anos": 12, "mes": 1, "meses": 1,
              "cuatrimestre": 4, "cuatrimestres": 4,
              "semestre": 6, "semestres": 6}[unit]
    return round(float(match.group(1).replace(",", ".")) * factor)


def modality(value: str | None) -> str | None:
    key = comparison_key(value)
    if not key:
        return None
    in_person = "presencial" in key
    remote = any(word in key for word in ("virtual", "online", "distancia", "remoto"))
    if "semipresencial" in key or "hibrid" in key or (in_person and remote):
        return "Híbrida"
    if in_person:
        return "Presencial"
    if remote:
        return "Virtual"
    return None


# The plan documents are visual charts, and the text of a chart comes out in
# the order the PDF stores its blocks, not the order it is read: the year
# headings appear detached from their subjects, sometimes all at the top and
# sometimes with the fifth year before the fourth. Assigning a year from that
# order would be inventing one, so the subjects are kept without it.
# Two header formats are published. A degree writes them in one sentence and a
# postgraduate document labels each line on its own.
_PLAN_HEADER = re.compile(
    r"Carrera\s*:\s*([^.]{2,90})\.\s*T[íi]tulo\s*:\s*([^.]{2,90})\.", re.I
)
_PLAN_AWARDED = re.compile(r"T[ÍI]TULO\s+A\s+OTORGAR\s*:\s*([^\n]{3,90})", re.I)
_PLAN_DURATION = re.compile(r"A[ÑN]OS\s+DE\s+DURACI[ÓO]N\s*:\s*([^\n]{1,30})", re.I)
_PLAN_MODALITY = re.compile(r"MODALIDAD\s*:\s*([^\n]{3,60})", re.I)
_PLAN_YEAR = re.compile(r"^\d\s*[ºo°]\s*A[ÑN]O\b", re.I)
_PLAN_NOISE = re.compile(
    r"^[^\wÁÉÍÓÚÑáéíóúñ]+$"
    r"|^(plan de estudios|referencias|track\b|electivas?\b|optativas?\b)"
    r"|^(primer|segundo|tercer|cuarto|quinto)\s+(cuatrimestre|semestre)\b",
    re.I,
)


def pdf_text(pdf_bytes: bytes) -> str:
    from io import BytesIO

    from pypdf import PdfReader

    try:
        return "\n".join(
            page.extract_text() or "" for page in PdfReader(BytesIO(pdf_bytes)).pages
        )
    except Exception:
        return ""


def parse_plan_pdf_degree(pdf_bytes: bytes) -> str | None:
    """Read the degree the plan states the programme awards."""
    text = pdf_text(pdf_bytes)
    match = _PLAN_HEADER.search(text)
    if match:
        return clean_text(match.group(2))
    labelled = _PLAN_AWARDED.search(text)
    return clean_text(labelled.group(1)).rstrip(".,;") if labelled else None


def parse_plan_pdf_facts(pdf_bytes: bytes) -> dict[str, str]:
    """Read the length and the modality when the document labels them."""
    text = pdf_text(pdf_bytes)
    facts: dict[str, str] = {}
    for key, pattern in (("duracion", _PLAN_DURATION), ("modalidad", _PLAN_MODALITY)):
        match = pattern.search(text)
        if match:
            value = clean_text(match.group(1)).rstrip(".,;")
            if value:
                facts[key] = value
    return facts


def parse_plan_pdf(pdf_bytes: bytes, programme: str) -> list[dict[str, Any]]:
    """Read the subjects a plan document lists, without a year."""
    subjects: list[dict[str, Any]] = []
    seen: set[str] = set()
    started = False
    for raw in pdf_text(pdf_bytes).splitlines():
        line = clean_text(raw)
        if not line or _PLAN_NOISE.match(line):
            continue
        if _PLAN_YEAR.match(line):
            started = True
            continue
        # Everything before the first year heading is the cover, and the chart
        # carries side notes written as sentences: a subject is a short name,
        # not a phrase that closes with a full stop or opens in lower case.
        if not started or len(line) > 70 or line.endswith(".") or not line[0].isupper():
            continue
        key = comparison_key(line)
        if key in seen:
            continue
        seen.add(key)
        subjects.append(blank_record(
            "materias", universidad_nombre=UNIVERSITY,
            carrera_o_programa=programme, nombre_materia=line,
            anio_cursada=None, turno=None, area_tematica=None,
            descripcion_breve=None, regimen=None, carga_horaria_semanal=None,
        ))
    return subjects


def build_dataset(
    programmes: tuple[ProgrammeRef, ...],
    programme_pages: dict[str, str],
    plan_documents: dict[str, bytes] | None = None,
    people: list[dict[str, Any]] | None = None,
    authorities: list[dict[str, Any]] | None = None,
    campuses: tuple[str, ...] = (),
    areas: tuple[str, ...] = (),
    excluded: list[dict[str, str]] | None = None,
    errors: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Assemble the Austral dataset from the catalogue and the pages."""
    data: dict[str, list[dict[str, Any]]] = {section: [] for section in SECTION_FIELDS}
    data["universidades"] = [blank_record(
        "universidades", nombre_oficial=UNIVERSITY, nombre_corto=SHORT_NAME,
        tipo_gestion="Privada", sitio_web=BASE_URL,
    )]
    # The taxonomy writes them in capitals; the offers reference the readable
    # form, so both have to be built the same way.
    data["sedes"] = [blank_record(
        "sedes", universidad_nombre=UNIVERSITY, nombre_sede=_campus_name(name),
        localidad=None,
        # The campus taxonomy names the sites; their addresses are not part of
        # the catalogue and are not asserted here.
        calle=None, numero=None, tipo_sede="Otro",
    ) for name in campuses]
    data["facultades"] = [blank_record(
        "facultades", universidad_nombre=UNIVERSITY, nombre_facultad=name,
        tipo_unidad="Facultad", sede=None,
    ) for name in areas]
    data["autoridades"] = list(authorities or [])

    details: list[dict[str, Any]] = []
    resources: list[dict[str, Any]] = []
    missing_pages = list(excluded or [])
    # Austral publishes a programme once per campus, and sometimes twice at the
    # same campus through a landing page. The contract keeps one programme and
    # one offer per campus, so the entries are grouped by name and the richest
    # page of each group describes it.
    by_name: dict[str, list[dict[str, Any]]] = {}
    for ref in programmes:
        html = programme_pages.get(ref.url, "")
        if not html:
            missing_pages.append({"nombre": ref.name, "url": ref.url,
                                  "motivo": "la página no se pudo descargar"})
            continue
        attendance = parse_attendance(html)
        document = (plan_documents or {}).get(ref.url, b"")
        awarded = parse_plan_pdf_degree(document) if document else None
        document_facts = parse_plan_pdf_facts(document) if document else {}
        detail = {
            "name": ref.name, "level": ref.level, "kind": ref.kind, "url": ref.url,
            "area": ref.area, "campus": ref.campus,
            "start": attendance.get("inicio"),
            # The page states these; the plan document repeats them for the
            # programmes whose page does not.
            "duration": attendance.get("duracion") or document_facts.get("duracion"),
            "modality": attendance.get("modalidad") or document_facts.get("modalidad"),
            "published_campus": attendance.get("sede"),
            "awarded_degree": awarded,
            "description": _description(html),
        }
        detail["document"] = document
        detail["ref"] = ref
        details.append(detail)
        by_name.setdefault(comparison_key(ref.name), []).append(detail)

    for group in by_name.values():
        detail = max(group, key=_published_facts)
        ref = detail["ref"]
        document = detail["document"]
        awarded = detail["awarded_degree"]
        subjects = parse_plan_pdf(document, ref.name) if document else []
        data["materias"].extend(subjects)
        html = programme_pages.get(ref.url, "")
        if ref.level == "Grado":
            data["carreras"].append(blank_record(
                "carreras", universidad_nombre=UNIVERSITY, facultad_nombre=ref.area,
                nombre_carrera=ref.name, denominacion_canonica=ref.name, nivel="Grado",
                titulo_otorgado=awarded, tiene_titulo_intermedio=None,
                duracion_anios=duration_years(detail["duration"]),
                descripcion_breve=detail["description"],
                cantidad_materias_total=len(subjects) or None,
            ))
            # One offer per campus the programme is published at.
            for campus in sorted({item["ref"].campus for item in group}):
                published = next(
                    item for item in group if item["ref"].campus == campus
                )
                data["ofertas"].append(blank_record(
                    "ofertas", universidad_nombre=UNIVERSITY, facultad_nombre=ref.area,
                    carrera_nombre=ref.name, sede=campus,
                    modalidad=modality(published["modality"]), regimen_ingreso=None,
                    coneau_resolucion=None, coneau_vigencia_hasta=None,
                    tiene_pasantias=None, tiene_bolsa_trabajo=None,
                    url_oficial=published["ref"].url,
                ))
        else:
            data["posgrados"].append(blank_record(
                "posgrados", universidad_nombre=UNIVERSITY, facultad_nombre=ref.area,
                nombre_programa=ref.name, tipo_posgrado=ref.kind,
                titulo_otorgado=awarded, sede=ref.campus,
                modalidad=modality(detail["modality"]),
                duracion_meses=duration_months(detail["duration"]),
                requiere_tesis_trabajo_final=None, requisito_titulo_previo=None,
                cohorte_inicio=detail["start"], costo_total_programa=None,
                moneda=None, descripcion_breve=detail["description"],
                url_oficial=ref.url,
            ))
        if document:
            resources.append({
                "entidad_tipo": "carrera" if ref.level == "Grado" else "posgrado",
                "entidad_nombre": ref.name, "tipo_recurso": "documento",
                "titulo": f"Plan de estudios de {ref.name}",
                "url": plan_document_url(html) if html else None,
                "fuente_url": ref.url,
            })

    merged = [
        {"nombre": group[0]["ref"].name,
         "urls": [item["ref"].url for item in group],
         "motivo": "el catálogo lo publica más de una vez"}
        for group in by_name.values() if len(group) > 1
    ]
    missing = [section for section, rows in data.items() if not rows]
    return {
        "universidad": UNIVERSITY,
        "fuente_principal": BASE_URL,
        "extraido_en": datetime.now(timezone.utc).isoformat(),
        "metodo": "API REST pública de WordPress y HTML; sin IA",
        "datos": data,
        "recursos_publicos": resources,
        # The working entries carry the downloaded document and the catalogue
        # reference; neither belongs in the artifact.
        "detalle_programas": [
            {key: value for key, value in detail.items()
             if key not in ("document", "ref")}
            for detail in details
        ],
        "directorio_academico": {"personas": list(people or []), "roles_academicos": []},
        "control_calidad": {
            "secciones_vacias": missing,
            "programas_descubiertos": len(programmes),
            "programas_excluidos": missing_pages,
            "programas_unificados": merged,
            "materias_sin_anio": {
                "motivo": "los planes se publican como cuadros en PDF y el texto "
                          "extraído no conserva el orden visual, así que el año no "
                          "puede leerse sin inventarlo",
            },
            "errores_descarga": errors or [],
            "nota": "Los valores ausentes permanecen nulos; no se inventan datos.",
        },
    }


def _published_facts(detail: dict[str, Any]) -> tuple[int, int, int]:
    """Rank an entry by how much the page actually publishes."""
    return (
        1 if detail.get("document") else 0,
        sum(1 for key in ("start", "duration", "modality") if detail.get(key)),
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
