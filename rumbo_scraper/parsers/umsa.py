"""Deterministic parsers for Universidad del Museo Social Argentino.

The site is WordPress and publishes its catalogue through the REST API as two
custom post types: `carrera`, which the university classifies as grado or
posgrado, and `oferta`, which gathers everything shorter. The taxonomy says
what each one is, so nothing is read out of a name.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any

from bs4 import BeautifulSoup

from rumbo_scraper.contracts import SECTION_FIELDS, blank_record
from rumbo_scraper.normalizers.text import clean_text, comparison_key

UNIVERSITY = "Universidad del Museo Social Argentino"
SHORT_NAME = "UMSA"
BASE_URL = "https://www.umsa.edu.ar"
API_URL = f"{BASE_URL}/wp-json/wp/v2"
DOMAIN = "umsa.edu.ar"

# The taxonomy writes the kinds in plural; the contract uses the singular.
POSTGRADUATE_KINDS = {
    "doctorados": "Doctorado",
    "maestrias": "Maestría",
    "especializaciones": "Especialización",
    "diplomaturas": "Diplomatura",
}
# Of everything published as `oferta`, only a diplomatura is a postgraduate
# degree in the contract; the rest are courses, workshops and seminars.
OFFER_AS_POSTGRADUATE = {"diplomatura": "Diplomatura"}


@dataclass(frozen=True)
class ProgrammeRef:
    """A programme as the catalogue publishes it."""

    name: str
    url: str
    level: str
    kind: str | None
    faculty: str | None


def _plain(value: Any) -> str | None:
    if value is None:
        return None
    text = clean_text(BeautifulSoup(str(value), "html.parser").get_text(" ", strip=True))
    return text or None


def discover_programmes(
    careers: list[dict[str, Any]],
    offers: list[dict[str, Any]],
    titles: dict[int, str],
    postgraduate_kinds: dict[int, str],
    faculties: dict[int, str],
    offer_kinds: dict[int, str],
) -> tuple[tuple[ProgrammeRef, ...], list[dict[str, str]]]:
    """Split the catalogue into the programmes the contract models."""
    refs: list[ProgrammeRef] = []
    excluded: list[dict[str, str]] = []
    seen: set[str] = set()

    def add(name: str | None, url: str, level: str | None, kind: str | None,
            faculty: str | None, reason: str) -> None:
        if not name or not url or url in seen:
            return
        seen.add(url)
        if level is None:
            excluded.append({"nombre": name, "url": url, "motivo": reason})
            return
        refs.append(ProgrammeRef(name, url, level, kind, faculty))

    for item in careers:
        name = _plain((item.get("title") or {}).get("rendered"))
        url = clean_text(str(item.get("link") or ""))
        faculty = next((faculties.get(t) for t in item.get("facultad") or []), None)
        published = next((titles.get(t) for t in item.get("tipo-de-titulo") or []), None)
        key = comparison_key(published)
        if key == "grado":
            add(name, url, "Grado", None, faculty, "")
        elif key == "posgrado":
            kind = next(
                (POSTGRADUATE_KINDS.get(comparison_key(postgraduate_kinds.get(t)))
                 for t in item.get("tipo-de-posgrado") or []), None
            )
            add(name, url, "Posgrado", kind, faculty, "")
        else:
            add(name, url, None, None, faculty,
                f"el catálogo lo clasifica como {published or 'sin tipo de título'}")

    for item in offers:
        name = _plain((item.get("title") or {}).get("rendered"))
        url = clean_text(str(item.get("link") or ""))
        faculty = next((faculties.get(t) for t in item.get("facultad") or []), None)
        published = next((offer_kinds.get(t) for t in item.get("tipo-de-oferta") or []), None)
        kind = OFFER_AS_POSTGRADUATE.get(comparison_key(published))
        add(name, url, "Posgrado" if kind else None, kind, faculty,
            f"el catálogo lo clasifica como {published or 'sin tipo de oferta'}")

    return tuple(sorted(refs, key=lambda ref: comparison_key(ref.name))), excluded


def _soup(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style", "noscript"]):
        element.decompose()
    return soup


def parse_labelled_columns(html: str) -> dict[str, str]:
    """Read the header/value rows the programme pages publish.

    The page lays a row of labels over a row of values: "Duración | Título"
    above "2 años de cursada | Doctor/a en Ciencias Jurídicas".
    """
    values: dict[str, str] = {}
    for row in _soup(html).find_all("div", class_="row"):
        labels = [clean_text(col.get_text(" ", strip=True))
                  for col in row.find_all("div", class_="col", recursive=False)]
        if len(labels) < 2 or not all(labels):
            continue
        if not all(len(label) <= 24 for label in labels):
            continue
        following = row.find_next_sibling("div")
        if following is None:
            continue
        cells = [clean_text(col.get_text(" ", strip=True))
                 for col in following.find_all("div", class_="col", recursive=False)]
        if len(cells) != len(labels):
            continue
        for label, value in zip(labels, cells, strict=True):
            if value:
                values.setdefault(comparison_key(label), value)
    return values


def parse_labelled_text(html: str, label: str) -> str | None:
    """Read a labelled fact written inline.

    The page writes "Duración: 2 años" with a colon and "MODALIDAD A distancia"
    without one, so the separator is optional and the value ends where the next
    heading in capitals begins.
    """
    text = clean_text(_soup(html).get_text(" ", strip=True))
    # Only the label ignores case: the value ends where the next heading in
    # capitals begins, and a case-insensitive terminator would cut it at the
    # first ordinary word.
    others = "|".join(("Duraci[óo]n", "T[íi]tulo", "Modalidad", "Sede", "Inicio"))
    match = re.search(
        rf"\b(?i:{label})\s*:?\s+(.{{1,60}}?)\s*"
        rf"(?=\s(?i:{others})\s*:|\s[A-ZÁÉÍÓÚ]{{3,}}|$)",
        text,
    )
    return clean_text(match.group(1)).rstrip(".,;") if match else None


# A cycle names its year either in digits, "(1 AÑO)", or in words, as the
# degree plans do: "PRIMER AÑO".
_CYCLE_YEAR = re.compile(r"\(?\s*(\d+)\s*(?:º|°)?\s*A[ÑN]O", re.I)
_CYCLE_WORD_YEAR = re.compile(
    r"\b(PRIMER|SEGUNDO|TERCER|CUARTO|QUINTO|SEXTO)\s+A[ÑN]O\b", re.I
)
_WORD_YEARS = {"primer": 1, "segundo": 2, "tercer": 3, "cuarto": 4,
               "quinto": 5, "sexto": 6}


def parse_study_plan(html: str, programme: str) -> list[dict[str, Any]]:
    """Read the plan, published as one table per cycle."""
    soup = _soup(html)
    subjects: list[dict[str, Any]] = []
    seen: set[tuple[str, int | None]] = set()
    for table in soup.find_all("table"):
        heading = table.find_previous(["p", "h2", "h3", "h4", "strong"])
        label = clean_text(heading.get_text(" ", strip=True)) if heading else ""
        # A cycle names its year when it has one: "CICLO DE FORMACIÓN GENERAL
        # (1 AÑO)". A cycle without a year leaves the subject without one.
        year_match = _CYCLE_YEAR.search(label)
        word_match = _CYCLE_WORD_YEAR.search(label)
        if year_match:
            year = int(year_match.group(1))
        elif word_match:
            year = _WORD_YEARS[comparison_key(word_match.group(1))]
        else:
            year = None
        for row in table.find_all("tr"):
            cells = [clean_text(cell.get_text(" ", strip=True))
                     for cell in row.find_all(["td", "th"])]
            name = next((cell for cell in cells if len(cell) >= 3), "")
            if not name or name.isupper():
                continue
            # A second column states how the subject runs.
            regime = next(
                (cell for cell in cells[1:]
                 if comparison_key(cell) in ("anual", "cuatrimestral", "semestral",
                                             "trimestral", "bimestral")),
                None,
            )
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
    # Both forms are published, and stripping a trailing "s" turns "meses"
    # into "mese", so every form is listed.
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
    remote = any(word in key for word in ("distancia", "virtual", "online", "remoto"))
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
    faculties: tuple[str, ...] = (),
    excluded: list[dict[str, str]] | None = None,
    errors: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Assemble the UMSA dataset from the catalogue and the pages."""
    data: dict[str, list[dict[str, Any]]] = {section: [] for section in SECTION_FIELDS}
    data["universidades"] = [blank_record(
        "universidades", nombre_oficial=UNIVERSITY, nombre_corto=SHORT_NAME,
        tipo_gestion="Privada", sitio_web=BASE_URL,
    )]
    data["facultades"] = [blank_record(
        "facultades", universidad_nombre=UNIVERSITY, nombre_facultad=name,
        tipo_unidad="Facultad", sede=None,
    ) for name in faculties]

    details: list[dict[str, Any]] = []
    missing_pages = list(excluded or [])
    # The same programme is published more than once: a diplomatura once per
    # cohort, and the Doctorado once per modality. The contract keeps one row
    # per name, so the entries are grouped and the page that publishes the most
    # describes it.
    by_name: dict[str, list[dict[str, Any]]] = {}
    for ref in programmes:
        html = programme_pages.get(ref.url, "")
        if not html:
            missing_pages.append({"nombre": ref.name, "url": ref.url,
                                  "motivo": "la página no se pudo descargar"})
            continue
        columns = parse_labelled_columns(html)
        published_modality = parse_labelled_text(html, "MODALIDAD")
        duration = columns.get("duracion") or parse_labelled_text(html, "Duración")
        detail = {
            "name": ref.name, "level": ref.level, "kind": ref.kind, "url": ref.url,
            "faculty": ref.faculty, "duration": duration,
            "awarded_degree": columns.get("titulo"),
            "modality": published_modality,
            "description": _description(html),
        }
        detail["ref"] = ref
        detail["html"] = html
        details.append(detail)
        by_name.setdefault(comparison_key(ref.name), []).append(detail)

    for group in by_name.values():
        detail = max(group, key=_published_facts)
        ref = detail["ref"]
        html = detail["html"]
        subjects = parse_study_plan(html, ref.name)
        data["materias"].extend(subjects)
        if ref.level == "Grado":
            data["carreras"].append(blank_record(
                "carreras", universidad_nombre=UNIVERSITY, facultad_nombre=ref.faculty,
                nombre_carrera=ref.name, denominacion_canonica=ref.name, nivel="Grado",
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
    """Rank an entry by how much its page actually publishes."""
    return (
        sum(1 for key in ("duration", "awarded_degree", "modality") if detail.get(key)),
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
