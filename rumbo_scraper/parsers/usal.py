"""Deterministic parsers for the public site of the USAL.

The Universidad del Salvador keeps two indexes, one of careers and one of
postgraduate programmes, and a page per programme under the section of the
faculty that teaches it. The page opens with the faculty, the name and a
sentence, states the degree with its length in brackets -- ``Contador Público
(4 años)`` -- and prints the CONEAU resolution of each campus.

It is also the only site of the ten that publishes what a career costs, in a
table of its own, so ``aranceles`` is filled here for the first time.
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

UNIVERSITY = "Universidad del Salvador"
SHORT_NAME = "USAL"
BASE_URL = "https://www.usal.edu.ar"
DOMAIN = "usal.edu.ar"

INDEXES: tuple[tuple[str, str], ...] = (
    (f"{BASE_URL}/carreras-de-grado", "Grado"),
    (f"{BASE_URL}/posgrados", "Posgrado"),
)
INDEX_URLS = tuple(url for url, _ in INDEXES)

# A link is a programme when its text opens with the kind of degree it is and
# its address is one of the pages the site keeps per programme.
_PROGRAMME_LABEL = re.compile(
    r"(?i)^(licenciatura|ingenier[íi]a|abogac[íi]a|contador|medicina|"
    r"profesorado|tecnicatura|arquitectura|traductorado|maestr[íi]a|"
    r"doctorado|especializaci[óo]n|diplomatura)\b"
)
_PROGRAMME_PATH = re.compile(r"^/[^/]+/propuesta/[^/]+/?$")

POSTGRADUATE_KINDS = (
    ("doctorado", "Doctorado"),
    ("maestria", "Maestría"),
    ("magister", "Maestría"),
    ("especializacion", "Especialización"),
    ("diplomatura", "Diplomatura"),
)


@dataclass(frozen=True)
class ProgrammeRef:
    """A programme as one of the two indexes publishes it."""

    name: str
    url: str
    level: str


def _soup(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style", "noscript"]):
        element.decompose()
    return soup


def discover_programmes(pages: dict[str, str]) -> tuple[ProgrammeRef, ...]:
    """Read the programmes the two indexes link, keeping the first level."""
    level_of = dict(INDEXES)
    refs: dict[str, ProgrammeRef] = {}
    for index_url, html in pages.items():
        level = level_of.get(index_url)
        if not level or not html:
            continue
        for anchor in _soup(html).find_all("a", href=True):
            name = clean_text(anchor.get_text(" ", strip=True))
            if not _PROGRAMME_LABEL.match(name) or len(name) > 110:
                continue
            url = urljoin(index_url, clean_text(anchor["href"]))
            parsed = urlparse(url)
            if parsed.netloc.lower().lstrip("www.") != DOMAIN:
                continue
            if not _PROGRAMME_PATH.match(parsed.path):
                continue
            refs.setdefault(comparison_key(name),
                            ProgrammeRef(name, f"{BASE_URL}{parsed.path}", level))
    return tuple(refs.values())


_FACULTY = re.compile(r"^(facultad|escuela)\s+de\s+\w")


def faculty_name(html: str) -> str | None:
    """The faculty the page names above the programme."""
    # The shortest node that opens with the word is the name alone; a longer
    # one has swallowed the paragraph beside it.
    found: list[str] = []
    for node in _soup(html).find_all(["h1", "h2", "h3", "p", "div", "span"]):
        text = clean_text(node.get_text(" ", strip=True))
        # "Facultades" alone is the menu; a faculty always names itself.
        if 14 <= len(text) <= 90 and _FACULTY.match(comparison_key(text)):
            found.append(text)
    return min(found, key=len) if found else None


# The page writes the degree and, in brackets beside it, how long it takes.
_DEGREE = re.compile(r"(?i)t[íi]tulo\s*:?\s*")
_YEARS_IN_BRACKETS = re.compile(r"\((\d+(?:[.,]\d+)?)\s*a[ñn]os?\)")
_CONEAU = re.compile(r"(RESFC-\d{4}-\d+-?\s*APN-CONEAU#ME|"
                     r"RES(?:OLUCI[ÓO]N)?\.?\s*(?:CONEAU\s*)?N?[º°]?\s*\d+/\d+)", re.I)


def parse_facts(html: str) -> dict[str, str]:
    """Read the degree, its length and the accreditation the page prints."""
    soup = _soup(html)
    for element in soup(["nav", "footer", "header"]):
        element.decompose()
    lines = [clean_text(line) for line in soup.get_text("\n").split("\n")]
    lines = [line for line in lines if line]
    facts: dict[str, str] = {}
    for position, line in enumerate(lines):
        if _DEGREE.fullmatch(line) and position + 1 < len(lines):
            facts.setdefault("titulo", lines[position + 1])
        if "duracion" not in facts:
            years = _YEARS_IN_BRACKETS.search(line)
            if years:
                facts["duracion"] = years.group(1)
        if "coneau" not in facts:
            accreditation = _CONEAU.search(line)
            if accreditation:
                facts["coneau"] = clean_text(accreditation.group(1))
    return facts


_FEES = re.compile(r"(?i)\baranceles?\b")
_AMOUNT = re.compile(r"\$\s*([\d.]+)")
_FEE_LABELS = (
    ("matr[íi]cula", "monto_matricula"),
    ("cuotas? mensuales", "monto_mensual"),
    ("cuota", "monto_mensual"),
    ("derecho de inscripci[óo]n", "monto_inscripcion"),
)


def parse_fees(html: str) -> dict[str, Any]:
    """Read the table of fees the page publishes, when it publishes one.

    The amounts are written as ``$ 759.957`` with a dot for the thousands, so
    the dot is removed before the number is read.
    """
    for table in _soup(html).find_all("table"):
        text = clean_text(table.get_text(" ", strip=True))
        if not _FEES.search(text):
            continue
        fees: dict[str, Any] = {"detalle": text[:300]}
        for pattern, key in _FEE_LABELS:
            match = re.search(rf"(?i){pattern}[^$]{{0,40}}\$\s*([\d.]+)", text)
            if match and key not in fees:
                fees[key] = int(match.group(1).replace(".", ""))
        period = re.search(r"(?i)ingreso\s+([^()]{3,40}?)\s*\(", text)
        if period:
            fees["vigencia"] = clean_text(period.group(1))
        if len(fees) > 1:
            return fees
    return {}


def description(html: str) -> str | None:
    soup = _soup(html)
    for meta in soup.find_all("meta"):
        if (meta.get("name") or meta.get("property")) in ("description", "og:description"):
            value = clean_text(str(meta.get("content") or ""))
            if len(value) >= 40:
                return value
    for paragraph in soup.find_all("p"):
        value = clean_text(paragraph.get_text(" ", strip=True))
        if len(value) >= 120:
            return value
    return None


def duration_years(value: str | None) -> float | None:
    if not value:
        return None
    try:
        years = float(clean_text(value).replace(",", "."))
    except ValueError:
        return None
    return years if 0 < years <= 10 else None


def duration_months(value: str | None) -> int | None:
    years = duration_years(value)
    return round(years * 12) if years else None


def postgraduate_kind(name: str) -> str | None:
    key = comparison_key(name)
    for token, kind in POSTGRADUATE_KINDS:
        if re.search(rf"\b{token}", key):
            return kind
    return None


def modality(name: str) -> str | None:
    """The site writes the modality inside the name when it is not in person."""
    key = comparison_key(name)
    if "a distancia" in key:
        return "Virtual"
    if "semipresencial" in key:
        return "Híbrida"
    return None


def build_dataset(
    programmes: tuple[ProgrammeRef, ...],
    pages: dict[str, str],
    errors: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Assemble the USAL dataset from the page of every programme."""
    data: dict[str, list[dict[str, Any]]] = {section: [] for section in SECTION_FIELDS}
    data["universidades"] = [blank_record(
        "universidades", nombre_oficial=UNIVERSITY, nombre_corto=SHORT_NAME,
        tipo_gestion="Privada", sitio_web=BASE_URL,
    )]

    details: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    faculties: set[str] = set()
    for ref in programmes:
        html = pages.get(ref.url, "")
        if not html:
            excluded.append({"programa": ref.name, "url": ref.url,
                             "motivo": "la página no se pudo descargar"})
            continue
        facts = parse_facts(html)
        faculty = faculty_name(html)
        if faculty:
            faculties.add(faculty)
        fees = parse_fees(html)
        details.append({"nombre": ref.name, "nivel": ref.level, "facultad": faculty,
                        "url": ref.url, **facts,
                        "aranceles": bool(fees)})

        if ref.level == "Posgrado":
            data["posgrados"].append(blank_record(
                "posgrados", universidad_nombre=UNIVERSITY, facultad_nombre=faculty,
                nombre_programa=ref.name, tipo_posgrado=postgraduate_kind(ref.name),
                titulo_otorgado=facts.get("titulo"), sede=None,
                modalidad=modality(ref.name),
                duracion_meses=duration_months(facts.get("duracion")),
                requiere_tesis_trabajo_final=None, requisito_titulo_previo=None,
                cohorte_inicio=None, costo_total_programa=None, moneda=None,
                descripcion_breve=description(html), url_oficial=ref.url,
            ))
            continue
        data["carreras"].append(blank_record(
            "carreras", universidad_nombre=UNIVERSITY, facultad_nombre=faculty,
            nombre_carrera=ref.name, denominacion_canonica=ref.name, nivel="Grado",
            titulo_otorgado=facts.get("titulo"), tiene_titulo_intermedio=None,
            duracion_anios=duration_years(facts.get("duracion")),
            descripcion_breve=description(html), cantidad_materias_total=None,
        ))
        data["ofertas"].append(blank_record(
            "ofertas", universidad_nombre=UNIVERSITY, facultad_nombre=faculty,
            carrera_nombre=ref.name, sede=None, modalidad=modality(ref.name),
            regimen_ingreso=None, coneau_resolucion=facts.get("coneau"),
            coneau_vigencia_hasta=None, tiene_pasantias=None,
            tiene_bolsa_trabajo=None, url_oficial=ref.url,
        ))
        if fees:
            data["aranceles"].append(blank_record(
                "aranceles", universidad_nombre=UNIVERSITY, carrera_nombre=ref.name,
                sede=None, vigencia_desde=fees.get("vigencia"),
                monto_mensual=fees.get("monto_mensual"),
                monto_matricula=fees.get("monto_matricula"), moneda="ARS",
                motivo_cambio=None,
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
        "metodo": "HTML público de cada propuesta académica; sin IA",
        "datos": data,
        "recursos_publicos": [],
        "detalle_programas": details,
        "directorio_academico": {"personas": [], "roles_academicos": []},
        "control_calidad": {
            "secciones_vacias": missing,
            "secciones_sin_fuente_publica": {
                "materias": "la propuesta no publica el plan de estudios",
                "sedes": "la propuesta nombra las sedes en la resolución de "
                         "CONEAU, sin dirección",
                "turnos_anio": "no se publica un catálogo de horarios",
                "ofertas_ciclo": "no se publica un ciclo de inscripción",
                "areas_tematicas": "el catálogo no agrupa por área",
                "autoridades": "las autoridades se publican fuera del catálogo",
                "becas": "las becas se publican fuera del catálogo",
                "servicios_estudiantiles": "no hay catálogo de servicios",
                "actividades_extracurriculares": "no hay catálogo",
                "alojamiento": "no hay catálogo",
                "programas_internacionales": "no hay catálogo por carrera",
                "convenios_intercambio": "no hay catálogo por carrera",
                "redes_contacto": "no hay un directorio por facultad",
            },
            "programas_descubiertos": len(programmes),
            "programas_excluidos": excluded,
            "errores_descarga": errors or [],
            "nota": "Los valores ausentes permanecen nulos; no se inventan datos.",
        },
    }
