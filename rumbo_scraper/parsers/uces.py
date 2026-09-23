"""Deterministic parsers for the public site of UCES.

The site renders its catalogue from a block of data it prints inside the page
itself: ``laravel.data`` on the index of careers, grouped by faculty, and
``laravel.carrera`` on the page of each one. That block is the source read
here, because the page around it is a template the browser fills in and a
reader of the rendered text would find only its placeholders.

The block carries what the university publishes of a career: the degree it
awards, its intermediate degree, how long each takes, and the plan of studies
as HTML with a heading per year and a list item per subject. It also carries
the faculty with its address, its telephone and its mail.
"""

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

UNIVERSITY = "Universidad de Ciencias Empresariales y Sociales"
SHORT_NAME = "UCES"
BASE_URL = "https://www.uces.edu.ar"
DOMAIN = "uces.edu.ar"
CAREERS_URL = f"{BASE_URL}/carreras-universitarias"

_BLOCK = r"laravel\.{name}\s*=\s*({open}.*?{close});"


@dataclass(frozen=True)
class CareerRef:
    """A career as the index publishes it, under the faculty that teaches it."""

    name: str
    url: str
    faculty: str
    kind: str | None


def read_block(html: str, name: str, container: str = "{}") -> Any:
    """Read one of the blocks of data the page prints for its own scripts."""
    pattern = _BLOCK.format(name=name, open=re.escape(container[0]),
                            close=re.escape(container[1]))
    match = re.search(pattern, html or "", re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def discover_careers(html: str) -> tuple[CareerRef, ...]:
    """Read the careers the index groups by faculty."""
    data = read_block(html, "data") or {}
    refs: dict[str, CareerRef] = {}
    for faculty, careers in data.items():
        if not isinstance(careers, list):
            continue
        for career in careers:
            if not isinstance(career, dict):
                continue
            name = clean_text(career.get("titulo"))
            url = clean_text(career.get("url"))
            if not name or not url:
                continue
            refs.setdefault(comparison_key(name), CareerRef(
                name, urljoin(BASE_URL, url),
                _faculty_name(career.get("facultad"), faculty),
                clean_text(career.get("tipoCarrera")) or None,
            ))
    return tuple(refs.values())


def _faculty_name(faculty: object, fallback: str) -> str:
    if isinstance(faculty, dict):
        title = clean_text(faculty.get("title"))
        if title:
            return title
    return f"Facultad de {clean_text(fallback)}"


def read_faculties(html: str) -> list[dict[str, str]]:
    """Read the faculties the index describes, each with where it is."""
    data = read_block(html, "data") or {}
    faculties: dict[str, dict[str, str]] = {}
    for careers in data.values():
        for career in careers if isinstance(careers, list) else []:
            faculty = career.get("facultad") if isinstance(career, dict) else None
            if not isinstance(faculty, dict):
                continue
            name = clean_text(faculty.get("title"))
            if not name or name in faculties:
                continue
            faculties[name] = {
                "nombre": name,
                "direccion": clean_text(faculty.get("direccion")),
                "ciudad": clean_text(faculty.get("ciudad")),
                "provincia": clean_text(faculty.get("provincia")),
                "codigo_postal": clean_text(faculty.get("cp")),
                "telefono": clean_text(faculty.get("telefono")),
                "email": clean_text(faculty.get("email")),
            }
    return list(faculties.values())


def read_career(html: str) -> dict[str, Any]:
    """Read the block the page of a career prints with everything it states."""
    career = read_block(html, "carrera")
    return career if isinstance(career, dict) else {}


# The plan writes a heading per year and a list item per subject.
_PLAN_YEAR = re.compile(
    r"(?i)(primer|segundo|tercer|cuarto|quinto|sexto|s[ée]ptimo)\s+a[ñn]o"
    r"|\b([1-7])\s*[°ºa]?\s*a[ñn]o\b"
)
_YEAR_WORDS = {"primer": 1, "segundo": 2, "tercer": 3, "cuarto": 4,
               "quinto": 5, "sexto": 6, "septimo": 7}
_PLAN_TERM = re.compile(r"(?i)(primer|segundo|tercer)\s+(cuatrimestre|semestre)")
_TERMS = {"cuatrimestre": "Cuatrimestral", "semestre": "Semestral"}


def parse_plan(plan_html: str, career: str) -> list[dict[str, Any]]:
    """Read the subjects of the plan the block carries as HTML."""
    if not plan_html:
        return []
    soup = BeautifulSoup(plan_html, "html.parser")
    year: int | None = None
    regime: str | None = None
    subjects: list[dict[str, Any]] = []
    seen: set[str] = set()
    for node in soup.find_all(["h1", "h2", "h3", "h4", "h5", "p", "strong", "li"]):
        text = clean_text(node.get_text(" ", strip=True))
        if not text:
            continue
        if node.name != "li":
            heading = _PLAN_YEAR.search(text)
            if heading:
                word = comparison_key(heading.group(1) or "")
                year = _YEAR_WORDS.get(word) or (
                    int(heading.group(2)) if heading.group(2) else year)
            term = _PLAN_TERM.search(text)
            if term:
                regime = _TERMS.get(comparison_key(term.group(2)))
            continue
        if len(text) < 4 or comparison_key(text) in seen:
            continue
        seen.add(comparison_key(text))
        subjects.append(blank_record(
            "materias", universidad_nombre=UNIVERSITY, carrera_o_programa=career,
            nombre_materia=text, anio_cursada=year, turno=None, area_tematica=None,
            descripcion_breve=None, regimen=regime, carga_horaria_semanal=None,
        ))
    return subjects


def duration_years(value: object) -> float | None:
    match = re.search(r"(\d+(?:[.,]\d+)?)", clean_text(value))
    if not match:
        return None
    years = float(match.group(1).replace(",", "."))
    return years if 0 < years <= 10 else None


def _text(value: object) -> str | None:
    """The plain text of a field the block stores as HTML."""
    if not isinstance(value, str) or not value.strip():
        return None
    return clean_text(BeautifulSoup(value, "html.parser").get_text(" ", strip=True)) or None


def build_dataset(
    careers: tuple[CareerRef, ...],
    pages: dict[str, str],
    faculties: list[dict[str, str]] | None = None,
    errors: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Assemble the UCES dataset from the block of every career."""
    data: dict[str, list[dict[str, Any]]] = {section: [] for section in SECTION_FIELDS}
    data["universidades"] = [blank_record(
        "universidades", nombre_oficial=UNIVERSITY, nombre_corto=SHORT_NAME,
        tipo_gestion="Privada", sitio_web=BASE_URL,
    )]

    faculties = faculties or []
    localities: dict[str, dict[str, Any]] = {}
    for faculty in faculties:
        if faculty.get("ciudad"):
            key = f"{faculty['ciudad']}|{faculty.get('provincia')}"
            localities.setdefault(key, blank_record(
                "localidades", nombre_localidad=faculty["ciudad"],
                provincia=faculty.get("provincia") or None,
                codigo_postal=faculty.get("codigo_postal") or None,
            ))
        data["facultades"].append(blank_record(
            "facultades", universidad_nombre=UNIVERSITY,
            nombre_facultad=faculty["nombre"], tipo_unidad="Facultad",
            sede=faculty["nombre"],
        ))
        data["sedes"].append(blank_record(
            "sedes", universidad_nombre=UNIVERSITY, nombre_sede=faculty["nombre"],
            localidad=faculty.get("ciudad") or None,
            calle=_street(faculty.get("direccion")),
            numero=_number(faculty.get("direccion")), tipo_sede="Campus",
        ))
        for channel, key in (("Email", "email"), ("Teléfono", "telefono")):
            if faculty.get(key):
                data["redes_contacto"].append(blank_record(
                    "redes_contacto", universidad_nombre=UNIVERSITY,
                    facultad_nombre=faculty["nombre"], canal=channel,
                    usuario_o_direccion=faculty[key],
                ))
    data["localidades"] = list(localities.values())

    details: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    known = {row["nombre_facultad"] for row in data["facultades"]}
    for ref in careers:
        html = pages.get(ref.url, "")
        block = read_career(html) if html else {}
        if not block:
            excluded.append({"carrera": ref.name, "url": ref.url,
                             "motivo": "la página no publica los datos de la carrera"})
            continue
        subjects = parse_plan(str(block.get("planEstudios") or ""), ref.name)
        data["materias"].extend(subjects)
        faculty = ref.faculty if ref.faculty in known else None
        details.append({
            "nombre": ref.name, "facultad": ref.faculty, "url": ref.url,
            "tipo": ref.kind, "titulo": clean_text(block.get("tituloGrado")),
            "titulo_intermedio": clean_text(block.get("tituloIntermedio")),
            "duracion": clean_text(block.get("duracionTituloGrado")),
            "materias": len(subjects),
        })
        data["carreras"].append(blank_record(
            "carreras", universidad_nombre=UNIVERSITY, facultad_nombre=faculty,
            nombre_carrera=ref.name, denominacion_canonica=ref.name,
            nivel="Pregrado" if ref.kind == "tecnicatura" else "Grado",
            titulo_otorgado=clean_text(block.get("tituloGrado")) or None,
            tiene_titulo_intermedio=bool(clean_text(block.get("tituloIntermedio"))) or None,
            duracion_anios=duration_years(block.get("duracionTituloGrado")),
            descripcion_breve=_text(block.get("presentacionCopete"))
            or _text(block.get("presentacionTexto")),
            cantidad_materias_total=len(subjects) or None,
        ))
        data["ofertas"].append(blank_record(
            "ofertas", universidad_nombre=UNIVERSITY, facultad_nombre=faculty,
            carrera_nombre=ref.name, sede=faculty, modalidad=None,
            regimen_ingreso=None, coneau_resolucion=None,
            coneau_vigencia_hasta=None, tiene_pasantias=None,
            tiene_bolsa_trabajo=None, url_oficial=ref.url,
        ))

    missing = [section for section, rows in data.items() if not rows]
    return {
        "universidad": UNIVERSITY,
        "fuente_principal": CAREERS_URL,
        "extraido_en": datetime.now(timezone.utc).isoformat(),
        "metodo": "Bloque de datos que el sitio imprime en cada página; sin IA",
        "datos": data,
        "recursos_publicos": [],
        "detalle_carreras": details,
        "directorio_academico": {"personas": [], "roles_academicos": []},
        "control_calidad": {
            "secciones_vacias": missing,
            "secciones_sin_fuente_publica": {
                # The postgraduate catalogue is filled by a request the page
                # makes after loading and does not print its data in the HTML.
                "posgrados": "el listado de posgrados no viaja en la página; "
                             "la arma el navegador después de cargarla",
                "aranceles": "el arancel se publica como plantilla a completar",
                "turnos_anio": "los turnos se publican como plantilla a completar",
                "ofertas_ciclo": "no se publica un ciclo de inscripción",
                "areas_tematicas": "el plan no agrupa las materias por área",
                "autoridades": "las autoridades se publican fuera del catálogo",
                "becas": "las becas se publican fuera del catálogo",
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


def _street(address: str | None) -> str | None:
    value = clean_text(address)
    if not value:
        return None
    return clean_text(re.sub(r"\s*\d+\s*$", "", value)) or value


def _number(address: str | None) -> str | None:
    match = re.search(r"(\d+)\s*$", clean_text(address))
    return match.group(1) if match else None
