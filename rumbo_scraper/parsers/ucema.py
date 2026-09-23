"""Deterministic parsers for the public site of the UCEMA.

The site keeps its catalogue in two branches of its own sitemap, ``/grado``
and ``/posgrado``, one page per programme, and opens every page with the same
block of facts: what it awards, how it is taught, how long it lasts and the
resolution that recognises it officially.

The plan of studies is a section of prose and a leaflet in PDF, so the
subjects are not published as data and are declared instead of guessed.
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

UNIVERSITY = "Universidad del CEMA"
SHORT_NAME = "UCEMA"
BASE_URL = "https://ucema.edu.ar"
DOMAIN = "ucema.edu.ar"
# The sitemap is served in pages of two thousand addresses.
SITEMAP_URLS = tuple(f"{BASE_URL}/sitemap.xml?page={page}" for page in range(1, 5))

_GRADO = re.compile(r"^/grado/([^/]+)$")
_POSGRADO = re.compile(r"^/posgrado/([^/]+)$")

# Each fact is written as a label above its value, in the same box.
FACT_LABELS = {
    "titulacion": "titulacion",
    "modalidad": "modalidad",
    "duracion": "duracion",
    "reconocimiento oficial": "reconocimiento",
    "proximo inicio": "inicio",
}

POSTGRADUATE_KINDS = (
    ("doctorado", "Doctorado"),
    ("maestria", "Maestría"),
    ("magister", "Maestría"),
    ("mba", "Maestría"),
    ("especializacion", "Especialización"),
    ("diplomatura", "Diplomatura"),
)


@dataclass(frozen=True)
class ProgrammeRef:
    """A programme as the sitemap publishes it, with the branch it came from."""

    slug: str
    url: str
    level: str


def _soup(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style", "noscript"]):
        element.decompose()
    return soup


def discover_programmes(sitemaps: dict[str, str]) -> tuple[ProgrammeRef, ...]:
    """Read the programmes the sitemap lists, under the branch that holds them."""
    refs: dict[str, ProgrammeRef] = {}
    for sitemap in sitemaps.values():
        for url in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", sitemap or ""):
            parsed = urlparse(clean_text(url))
            if parsed.netloc.lower().lstrip("www.") != DOMAIN:
                continue
            grade = _GRADO.match(parsed.path)
            postgraduate = _POSGRADO.match(parsed.path)
            if grade:
                refs.setdefault(clean_text(url),
                                ProgrammeRef(grade.group(1), clean_text(url), "Grado"))
            elif postgraduate:
                refs.setdefault(clean_text(url), ProgrammeRef(
                    postgraduate.group(1), clean_text(url), "Posgrado"))
    return tuple(refs.values())


def programme_name(html: str, slug: str) -> str:
    """The name the page prints over the facts, or the one in its address."""
    heading = _soup(html).find("h1")
    name = clean_text(heading.get_text(" ", strip=True)) if heading else ""
    if name and len(name) > 3:
        return name
    words = clean_text(slug.replace("-", " "))
    minor = {"de", "del", "la", "las", "los", "y", "e", "en", "para"}
    return " ".join(
        word if index and word in minor else word.capitalize()
        for index, word in enumerate(words.split())
    )


def parse_facts(html: str) -> dict[str, str]:
    """Read the box of facts, where each label sits above its own value.

    The label is an element of its own and the value is the rest of the box
    that holds it, so the value is what is left after the label is removed.
    """
    facts: dict[str, str] = {}
    for label in _soup(html).select(".field-label-above"):
        key = FACT_LABELS.get(comparison_key(label.get_text(" ", strip=True)))
        parent = label.parent
        if not key or key in facts or parent is None:
            continue
        whole = clean_text(parent.get_text(" ", strip=True))
        heading = clean_text(label.get_text(" ", strip=True))
        value = clean_text(whole[len(heading):]) if whole.startswith(heading) else ""
        if value:
            facts[key] = value
    return facts


def description(html: str) -> str | None:
    """The sentence the page prints under the name of the programme."""
    soup = _soup(html)
    for meta in soup.find_all("meta"):
        if (meta.get("name") or meta.get("property")) in ("description", "og:description"):
            value = clean_text(str(meta.get("content") or ""))
            if len(value) >= 40:
                return value
    return None


def duration_years(value: str | None) -> float | None:
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*a[ñn]os?", value or "", re.I)
    return float(match.group(1).replace(",", ".")) if match else None


def duration_months(value: str | None) -> int | None:
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*(a[ñn]os?|mes(?:es)?|cuatrimestres?|"
                      r"bimestres?)", value or "", re.I)
    if not match:
        return None
    unit = comparison_key(match.group(2))
    factor = 12 if unit.startswith("ano") else (
        4 if unit.startswith("cuatri") else (2 if unit.startswith("bi") else 1))
    return round(float(match.group(1).replace(",", ".")) * factor)


def modality(value: str | None) -> str | None:
    key = comparison_key(value)
    if not key:
        return None
    in_person = "presencial" in key and "semipresencial" not in key
    remote = any(word in key for word in ("distancia", "online", "virtual", "remoto"))
    if "semipresencial" in key or "hibrid" in key or "blended" in key \
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
    programmes: tuple[ProgrammeRef, ...],
    pages: dict[str, str],
    errors: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Assemble the UCEMA dataset from the page of every programme."""
    data: dict[str, list[dict[str, Any]]] = {section: [] for section in SECTION_FIELDS}
    data["universidades"] = [blank_record(
        "universidades", nombre_oficial=UNIVERSITY, nombre_corto=SHORT_NAME,
        tipo_gestion="Privada", sitio_web=BASE_URL,
    )]

    details: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    seen: set[str] = set()
    for ref in programmes:
        html = pages.get(ref.url, "")
        if not html:
            excluded.append({"programa": ref.slug, "url": ref.url,
                             "motivo": "la página no se pudo descargar"})
            continue
        facts = parse_facts(html)
        if not facts.get("titulacion") and not facts.get("duracion"):
            # A page of the branch that states neither what it awards nor how
            # long it lasts is a landing, not a programme.
            excluded.append({"programa": ref.slug, "url": ref.url,
                             "motivo": "la página no publica datos del programa"})
            continue
        name = programme_name(html, ref.slug)
        if comparison_key(name) in seen:
            excluded.append({"programa": ref.slug, "url": ref.url,
                             "motivo": "el programa ya figura con otra dirección"})
            continue
        seen.add(comparison_key(name))
        details.append({"nombre": name, "nivel": ref.level, "url": ref.url, **facts})

        if ref.level == "Posgrado":
            data["posgrados"].append(blank_record(
                "posgrados", universidad_nombre=UNIVERSITY, facultad_nombre=None,
                nombre_programa=name, tipo_posgrado=postgraduate_kind(name),
                titulo_otorgado=facts.get("titulacion"), sede=None,
                modalidad=modality(facts.get("modalidad")),
                duracion_meses=duration_months(facts.get("duracion")),
                requiere_tesis_trabajo_final=None, requisito_titulo_previo=None,
                cohorte_inicio=facts.get("inicio"), costo_total_programa=None,
                moneda=None, descripcion_breve=description(html),
                url_oficial=ref.url,
            ))
            continue
        data["carreras"].append(blank_record(
            "carreras", universidad_nombre=UNIVERSITY, facultad_nombre=None,
            nombre_carrera=name, denominacion_canonica=name, nivel="Grado",
            titulo_otorgado=facts.get("titulacion"), tiene_titulo_intermedio=None,
            duracion_anios=duration_years(facts.get("duracion")),
            descripcion_breve=description(html), cantidad_materias_total=None,
        ))
        data["ofertas"].append(blank_record(
            "ofertas", universidad_nombre=UNIVERSITY, facultad_nombre=None,
            carrera_nombre=name, sede=None,
            modalidad=modality(facts.get("modalidad")), regimen_ingreso=None,
            # The site prints the resolution that recognises the programme
            # beside its name; it is the accreditation, not a CONEAU number.
            coneau_resolucion=facts.get("reconocimiento"),
            coneau_vigencia_hasta=None, tiene_pasantias=None,
            tiene_bolsa_trabajo=None, url_oficial=ref.url,
        ))

    missing = [section for section, rows in data.items() if not rows]
    return {
        "universidad": UNIVERSITY,
        "fuente_principal": BASE_URL,
        "extraido_en": datetime.now(timezone.utc).isoformat(),
        "metodo": "HTML público de cada carrera del sitemap; sin IA",
        "datos": data,
        "recursos_publicos": [],
        "detalle_programas": details,
        "directorio_academico": {"personas": [], "roles_academicos": []},
        "control_calidad": {
            "secciones_vacias": missing,
            "secciones_sin_fuente_publica": {
                "materias": "el plan de estudios se publica como prosa y como "
                            "folleto en PDF, no como listado de materias",
                "facultades": "la universidad no organiza su oferta por facultades",
                "sedes": "el catálogo no dice en qué sede se dicta cada carrera",
                "aranceles": "el arancel no se publica junto a la carrera",
                "turnos_anio": "no se publica un catálogo de horarios",
                "ofertas_ciclo": "se publica el próximo inicio, no un ciclo",
                "areas_tematicas": "el catálogo no agrupa por área",
                "autoridades": "las autoridades se publican fuera del catálogo",
                "becas": "las becas se publican fuera del catálogo",
                "servicios_estudiantiles": "no hay catálogo de servicios",
                "actividades_extracurriculares": "no hay catálogo",
                "alojamiento": "no hay catálogo",
                "programas_internacionales": "no hay catálogo",
                "convenios_intercambio": "no hay catálogo",
                "redes_contacto": "el directorio es por departamento, no por facultad",
            },
            "programas_descubiertos": len(programmes),
            "programas_excluidos": excluded,
            "errores_descarga": errors or [],
            "nota": "Los valores ausentes permanecen nulos; no se inventan datos.",
        },
    }
