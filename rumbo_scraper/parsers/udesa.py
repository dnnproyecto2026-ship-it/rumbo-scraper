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
            # The postgraduate plan is prose, not a table: it mixes subjects
            # with lecturers and instructions. Linking it keeps the evidence
            # without turning paragraphs into invented "materias" rows.
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
        "control_calidad": {
            "secciones_vacias": missing,
            "posgrados_descubiertos": len(postgraduate_refs),
            "posgrados_excluidos": excluded,
            "errores_descarga": errors or [],
            "campos_inferidos": [],
            "nota": "Los valores ausentes permanecen nulos; no se inventan datos.",
        },
    }
