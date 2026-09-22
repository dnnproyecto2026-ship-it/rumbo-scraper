"""Deterministic parsers for the public pages of ITBA.

The site is WordPress with a Divi theme: plain HTML for every programme page,
a sitemap that enumerates them and a menu, rendered by JavaScript, that
publishes the name of each one.
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

UNIVERSITY = "Instituto Tecnológico de Buenos Aires"
SHORT_NAME = "ITBA"
BASE_URL = "https://www.itba.edu.ar"
SITEMAP_URL = f"{BASE_URL}/wp-sitemap.xml"
DOMAIN = "itba.edu.ar"

# The menu writes every programme with the same abbreviations, and they also
# state the level: "Ing. Civil", "Lic. en Analítica", "Mtr. en Fintech".
ABBREVIATIONS: tuple[tuple[str, str, str], ...] = (
    ("Ing.", "Ingeniería", "Grado"),
    ("Lic.", "Licenciatura", "Grado"),
    ("Mtr.", "Maestría", "Posgrado"),
    ("Esp.", "Especialización", "Posgrado"),
    ("Dr.", "Doctorado", "Posgrado"),
)
POSTGRADUATE_KINDS = {
    "Maestría": "Maestría", "Especialización": "Especialización",
    "Doctorado": "Doctorado", "Diplomatura": "Diplomatura",
}

ATTENDANCE_LABELS = ("Duración", "Modalidad", "Sede", "Dedicación", "Inicio")

# Pages under /grado/ and /posgrado/ that are not programmes.
_PROGRAMME_PATH = re.compile(r"^/(grado|posgrado)/([a-z0-9\-]+)/?$")


@dataclass(frozen=True)
class ProgrammeRef:
    """A programme as the official menu publishes it."""

    name: str
    published_label: str
    url: str
    level: str
    kind: str | None


def expand_programme_name(label: str) -> tuple[str, str | None]:
    """Expand the abbreviations the menu publishes, leaving the rest verbatim.

    Each abbreviation is replaced where it stands, so "Ing. en Petróleo" keeps
    its preposition and "Mtr. y Esp. en Ciencia de Datos" keeps both degrees
    instead of being rebuilt into a phrase the university never wrote.
    """
    text = clean_text(label)
    kind: str | None = None
    for short, full, _level in ABBREVIATIONS:
        pattern = re.compile(rf"(?<![\w.]){re.escape(short)}(?=\s|$)")
        if pattern.search(text):
            text = pattern.sub(full, text)
            kind = kind or POSTGRADUATE_KINDS.get(full)
    return clean_text(text), kind


def programme_level(label: str, path_segment: str | None = None) -> str | None:
    """Read the level from the abbreviation, or from the section of the site.

    Most labels state it -- "Ing." is a degree, "Mtr." a postgraduate -- but a
    few are written without one, such as "Bioingeniería".
    """
    text = clean_text(label)
    for short, _full, level in ABBREVIATIONS:
        if re.search(rf"(?<![\w.]){re.escape(short)}(?=\s|$)", text):
            return level
    if path_segment == "grado":
        return "Grado"
    if path_segment == "posgrado":
        return "Posgrado"
    return None


def discover_programmes(menu_links: list[tuple[str, str]]) -> tuple[ProgrammeRef, ...]:
    """Enumerate the programmes the rendered menu links to.

    A link only counts when its path is a programme path and its label carries
    one of the published abbreviations, so a campaign page under the same
    prefix never becomes a degree.
    """
    refs: dict[str, ProgrammeRef] = {}
    for href, label in menu_links:
        path = urlparse(urljoin(BASE_URL, href)).path
        match = _PROGRAMME_PATH.match(path)
        if not match:
            continue
        level = programme_level(label, match.group(1))
        if level is None:
            continue
        # When the label states the level it has to agree with the section of
        # the site, so a postgraduate promoted on a degree page is not counted
        # twice under the wrong one.
        if (match.group(1) == "grado") != (level == "Grado"):
            continue
        name, kind = expand_programme_name(label)
        url = f"{BASE_URL}{path.rstrip('/')}/"
        refs.setdefault(url, ProgrammeRef(name, clean_text(label), url, level, kind))
    return tuple(sorted(refs.values(), key=lambda ref: comparison_key(ref.name)))


def _soup(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style", "noscript"]):
        element.decompose()
    return soup


def parse_attendance(html: str) -> dict[str, str]:
    """Read the labelled cells the programme strip publishes.

    The strip is anchored on "Duración": a page can carry another cell with the
    same label elsewhere -- the entry course also states a modality -- and only
    the row that states the length describes the programme itself. Reading the
    cells from the DOM rather than from the flattened text also keeps the
    footer, which lists every campus of the university, out of "Sede".
    """
    soup = _soup(html)
    anchor = soup.find(string=re.compile(r"^\s*Duración\s*:?\s*$"))
    if anchor is None:
        return _prose_attendance(soup)
    row = anchor.parent
    for _ in range(6):
        if row is None or row.parent is None:
            break
        row = row.parent
        if len(_cells(row)) >= 2:
            break
    return _cells(row) if row is not None else {}


def _cells(row: Any) -> dict[str, str]:
    """Pair each label with the value published beside it inside the row."""
    values: dict[str, str] = {}
    if row is None:
        return values
    for label in ATTENDANCE_LABELS:
        node = row.find(string=re.compile(rf"^\s*{label}\s*:?\s*$"))
        if node is None:
            continue
        column = node.parent
        # The label and its value sit in sibling blocks, so the value only
        # appears a few levels up, once the column that holds both is reached.
        for _ in range(5):
            if column is None:
                break
            text = clean_text(column.get_text(" ", strip=True))
            remainder = clean_text(re.sub(rf"^{label}\s*:?\s*", "", text))
            if remainder and comparison_key(remainder) not in {
                comparison_key(other) for other in ATTENDANCE_LABELS
            }:
                values[comparison_key(label)] = remainder
                break
            column = column.parent
    return values


def _prose_attendance(soup: BeautifulSoup) -> dict[str, str]:
    """Postgraduate pages write the same facts inside a paragraph."""
    text = clean_text(soup.get_text(" ", strip=True))
    values: dict[str, str] = {}
    others = "|".join(ATTENDANCE_LABELS)
    for label in ATTENDANCE_LABELS:
        match = re.search(
            rf"\b{label}\s*:\s*(.{{2,90}}?)\s*(?=\b(?:{others})\b\s*:|$)", text
        )
        if match:
            value = clean_text(match.group(1)).rstrip(".,;")
            if value:
                values[comparison_key(label)] = value
    return values


# What follows an awarded degree on these pages is its accreditation or the
# next labelled fact, so either one ends the value.
_AFTER_DEGREE = (
    r"Acreditad|Resoluci|CONEAU|Sesi[óo]n|Ministerio|\."
    r"|Modalidad|Duraci[óo]n|Inicio|Dedicaci[óo]n|Sede|D[íi]as|Vacantes|Plan"
)


def parse_labelled_prose(html: str, label: str) -> str | None:
    """Read "Label: value" where the page writes it inside a paragraph."""
    text = clean_text(_soup(html).get_text(" ", strip=True))
    match = re.search(rf"{label}\s*:\s*(.{{2,120}}?)\s*(?={_AFTER_DEGREE}|$)", text)
    return clean_text(match.group(1)).rstrip(".,;") if match else None


def duration_years(value: str | None) -> float | None:
    match = re.search(r"(\d+(?:[,.]\d+)?)\s*años?", value or "", re.I)
    return float(match.group(1).replace(",", ".")) if match else None


def duration_months(value: str | None) -> int | None:
    match = re.search(r"(\d+(?:[,.]\d+)?)\s*(años?|meses|cuatrimestres?)", value or "", re.I)
    if not match:
        return None
    unit = comparison_key(match.group(2))
    factor = 12 if unit.startswith("ano") else (4 if unit.startswith("cuatrimestre") else 1)
    return round(float(match.group(1).replace(",", ".")) * factor)


def parse_study_plan(html: str, programme: str) -> list[dict[str, Any]]:
    """Read the plan a degree page publishes as year blocks of term lists."""
    soup = _soup(html)
    subjects: list[dict[str, Any]] = []
    seen: set[tuple[str, int | None]] = set()
    for node in soup.find_all(string=re.compile(r"^\s*\d+\s*[°º]\s*año\s*$", re.I)):
        year_match = re.search(r"\d+", str(node))
        year = int(year_match.group()) if year_match else None
        container = node.parent
        for _ in range(6):
            if container is None or container.find_all(["ul", "ol"]):
                break
            container = container.parent
        if container is None:
            continue
        for group in container.find_all(["ul", "ol"]):
            for item in group.find_all("li"):
                name = clean_text(item.get_text(" ", strip=True)).lstrip("! ").strip()
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
                    descripcion_breve=None, regimen="Cuatrimestral",
                    carga_horaria_semanal=None,
                ))
    return subjects


CAMPUSES_URL = f"{BASE_URL}/la-universidad/institucional/sedes/"
AUTHORITIES_URL = f"{BASE_URL}/la-universidad/institucional/autoridades/"
TEACHERS_URL = f"{BASE_URL}/la-universidad/docentes/"
SCHOLARSHIPS_URL = f"{BASE_URL}/grado/becas/"
TEACHER_SITEMAP_URL = f"{BASE_URL}/wp-sitemap-posts-docente-1.xml"
PAGE_SITEMAP_URL = f"{BASE_URL}/wp-sitemap-posts-page-1.xml"

# Titles the authorities page prefixes to a name, in the capitals it uses.
_HONORIFIC = re.compile(
    r"^(ING|LIC|DR|DRA|MG|MAG|CDOR|CPN|ARQ|PROF|CN|SR|SRA)\.?\s+", re.I
)


def sitemap_urls(xml: str) -> list[str]:
    """Read the locations a WordPress sitemap publishes."""
    return [clean_text(loc) for loc in re.findall(r"<loc>([^<]+)</loc>", xml)]


def parse_campuses(html: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Read the campuses the institutional page publishes."""
    soup = _soup(html)
    localities: dict[tuple[str, str | None], dict[str, Any]] = {}
    campuses: list[dict[str, Any]] = []
    for heading in soup.find_all(["h2", "h3"]):
        name = clean_text(heading.get_text(" ", strip=True))
        if not name.lower().startswith(("sede", "campus", "nuevo campus")):
            continue
        # The address sits in the paragraph right after the heading.
        paragraph = heading.find_next("p")
        block = clean_text(paragraph.get_text(" ", strip=True)) if paragraph else ""
        street, number, locality, province = _address(block)
        if locality:
            localities[(locality, province)] = blank_record(
                "localidades", nombre_localidad=locality, provincia=province,
                codigo_postal=None,
            )
        campuses.append(blank_record(
            "sedes", universidad_nombre=UNIVERSITY, nombre_sede=name,
            localidad=f"{locality} — {province}" if locality else None,
            calle=street, numero=number,
            tipo_sede="Campus" if name.lower().startswith("campus") else "Otro",
        ))
    return list(localities.values()), campuses


def _address(text: str) -> tuple[str | None, str | None, str | None, str | None]:
    """Split "San Martín 202 Ciudad Autónoma de Buenos Aires"."""
    # The street is the words immediately before the number, not everything
    # that precedes it: the campus name sits on the same line.
    match = re.search(
        r"((?:[A-ZÁÉÍÓÚ][\w.áéíóúñ']*\s+){0,2}[A-ZÁÉÍÓÚ][\w.áéíóúñ']*)\s+(\d{1,5})\s+"
        r"(Ciudad Autónoma de Buenos Aires|CABA)",
        text,
    )
    if not match:
        return None, None, None, None
    street, number, locality = (clean_text(part) for part in match.groups())
    province = "CABA" if "buenos aires" in comparison_key(locality) and "ciudad" in comparison_key(locality) else None
    return street, number, locality, province


def parse_authorities(html: str) -> list[dict[str, Any]]:
    """Read the people the authorities page lists under each council."""
    soup = _soup(html)
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    section = None
    for heading in soup.find_all(["h2", "h3", "h4"]):
        text = clean_text(heading.get_text(" ", strip=True))
        if not text:
            continue
        stripped = _HONORIFIC.sub("", text)
        # The page marks a person by prefixing their academic title -- "ING.
        # SEBASTÍAN MUR". Without that marker a heading is the council it
        # introduces, or an item of the site menu, and never a person.
        if stripped != text:
            position = _position_after(heading)
            identity = (comparison_key(stripped), comparison_key(position or ""))
            if identity in seen:
                continue
            seen.add(identity)
            rows.append(blank_record(
                "autoridades", facultad_nombre=None, carrera=None,
                cargo=position or section or "Autoridad", tipo="Académico",
                nombre_autoridad=_titlecase(stripped),
            ))
        else:
            section = text
    return rows


def _position_after(heading: Any) -> str | None:
    node = heading.find_next(["p", "h5", "span"])
    value = clean_text(node.get_text(" ", strip=True)) if node else ""
    return value if 3 <= len(value) <= 90 else None


def _titlecase(name: str) -> str:
    """The page writes names in capitals; keep the words, restore the case."""
    minor = {"de", "del", "la", "las", "los", "y", "e"}
    words = [word.lower() for word in clean_text(name).split()]
    return " ".join(
        word if index and word in minor else word.capitalize()
        for index, word in enumerate(words)
    )


def parse_teacher_page(html: str, url: str) -> dict[str, Any] | None:
    """Read one teacher profile.

    The first heading of these pages is the generic label "Docente" and the
    name is the next one, so the document title is used instead: it reads
    "Cecilia Pedró | ITBA".
    """
    soup = _soup(html)
    title = clean_text(soup.title.get_text(strip=True)) if soup.title else ""
    name = clean_text(title.split("|")[0]) if title else ""
    if not name or comparison_key(name) in {"docente", "docentes", "itba"}:
        return None
    image = soup.find("img", src=True)
    return {
        "universidad_nombre": UNIVERSITY, "nombre_completo": name,
        "email": None, "perfil_url": url,
        "foto_url": image["src"] if image else None,
        "formacion": None, "biografia": None, "fuente_url": url,
    }


def build_dataset(
    programmes: tuple[ProgrammeRef, ...],
    programme_pages: dict[str, str],
    campuses_html: str = "",
    authorities_html: str = "",
    teacher_pages: dict[str, str] | None = None,
    errors: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Assemble the ITBA dataset from the pages that were downloaded."""
    data: dict[str, list[dict[str, Any]]] = {section: [] for section in SECTION_FIELDS}
    data["universidades"] = [blank_record(
        "universidades", nombre_oficial=UNIVERSITY, nombre_corto=SHORT_NAME,
        tipo_gestion="Privada", sitio_web=BASE_URL,
    )]
    data["localidades"], data["sedes"] = parse_campuses(campuses_html)
    data["autoridades"] = parse_authorities(authorities_html)

    details: list[dict[str, Any]] = []
    resources: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    for ref in programmes:
        html = programme_pages.get(ref.url)
        if not html:
            excluded.append({"nombre": ref.name, "url": ref.url,
                             "motivo": "la página no se pudo descargar"})
            continue
        attendance = parse_attendance(html)
        # A label without an abbreviation -- "Bioingeniería" -- is still a
        # programme, but so are the section pages under the same prefix. A
        # degree publishes the whole strip: how long it lasts and how it is
        # taught. The entry course states "Duración: 16 semanas" and nothing
        # else, which is why the length alone is not enough to tell them apart.
        if ref.kind is None and not (
            attendance.get("duracion") and attendance.get("modalidad")
        ):
            excluded.append({"nombre": ref.name, "url": ref.url,
                             "motivo": "la página no publica duración: no es un programa"})
            continue
        description = _description(html)
        detail = {
            "name": ref.name, "published_label": ref.published_label,
            "level": ref.level, "url": ref.url,
            "duration": attendance.get("duracion"),
            "modality": attendance.get("modalidad"),
            "dedication": attendance.get("dedicacion"),
            "start": attendance.get("inicio"),
            "description": description,
            "plan_url": _plan_url(html),
        }
        details.append(detail)
        if ref.level == "Grado":
            subjects = parse_study_plan(html, ref.name)
            data["materias"].extend(subjects)
            data["carreras"].append(blank_record(
                "carreras", universidad_nombre=UNIVERSITY, facultad_nombre=None,
                nombre_carrera=ref.name, denominacion_canonica=ref.name,
                nivel="Grado",
                # The pages state neither the awarded degree nor whether an
                # intermediate one exists.
                titulo_otorgado=None, tiene_titulo_intermedio=None,
                duracion_anios=duration_years(detail["duration"]),
                descripcion_breve=description,
                cantidad_materias_total=len(subjects) or None,
            ))
            data["ofertas"].append(blank_record(
                "ofertas", universidad_nombre=UNIVERSITY, facultad_nombre=None,
                # Every degree publishes "Multisede": taught across campuses
                # without saying which, so it is kept as published and never
                # resolved to one of them.
                carrera_nombre=ref.name, sede=attendance.get("sede"),
                modalidad=_modality(detail["modality"]), regimen_ingreso=None,
                coneau_resolucion=None, coneau_vigencia_hasta=None,
                tiene_pasantias=None, tiene_bolsa_trabajo=None,
                url_oficial=ref.url,
            ))
        else:
            data["posgrados"].append(blank_record(
                "posgrados", universidad_nombre=UNIVERSITY, facultad_nombre=None,
                nombre_programa=ref.name, tipo_posgrado=ref.kind,
                titulo_otorgado=parse_labelled_prose(html, "Título que otorga"),
                sede=None, modalidad=_modality(detail["modality"]),
                duracion_meses=duration_months(detail["duration"]),
                requiere_tesis_trabajo_final=None, requisito_titulo_previo=None,
                cohorte_inicio=detail["start"], costo_total_programa=None,
                moneda=None, descripcion_breve=description, url_oficial=ref.url,
            ))
        if detail["plan_url"]:
            # Most degrees publish the plan only as a PDF and this project has
            # no PDF pipeline, so the document is linked as evidence.
            resources.append({
                "entidad_tipo": "carrera" if ref.level == "Grado" else "posgrado",
                "entidad_nombre": ref.name, "tipo_recurso": "documento",
                "titulo": f"Plan de estudios de {ref.name}",
                "url": detail["plan_url"], "fuente_url": ref.url,
            })

    # Two profiles can publish the same name; the person is stored once.
    people: list[dict[str, Any]] = []
    seen_people: set[str] = set()
    for url, html in sorted((teacher_pages or {}).items()):
        person = parse_teacher_page(html, url)
        if not person:
            continue
        key = comparison_key(str(person["nombre_completo"]))
        if key in seen_people:
            continue
        seen_people.add(key)
        people.append(person)
    missing = [section for section, rows in data.items() if not rows]
    return {
        "universidad": UNIVERSITY,
        "fuente_principal": BASE_URL,
        "extraido_en": datetime.now(timezone.utc).isoformat(),
        "metodo": "HTML público de WordPress y menú renderizado; sin IA",
        "datos": data,
        "recursos_publicos": resources,
        "detalle_programas": details,
        "directorio_academico": {"personas": people, "roles_academicos": []},
        "control_calidad": {
            "secciones_vacias": missing,
            "programas_descubiertos": len(programmes),
            "programas_excluidos": excluded,
            "carreras_sin_plan_publicado": [
                detail["name"] for detail in details
                if detail["level"] == "Grado"
                and not any(row["carrera_o_programa"] == detail["name"]
                            for row in data["materias"])
            ],
            "errores_descarga": errors or [],
            "nota": "Los valores ausentes permanecen nulos; no se inventan datos.",
        },
    }


# These pages publish no meta description, so the first substantial paragraph
# is used: shorter ones are labels and navigation, not a description of the
# programme.
_DESCRIPTION_MIN_CHARS = 120


def _description(html: str) -> str | None:
    soup = _soup(html)
    for meta in soup.find_all("meta"):
        if (meta.get("name") or meta.get("property")) in ("description", "og:description"):
            value = clean_text(str(meta.get("content") or ""))
            if value:
                return value
    for paragraph in soup.find_all("p"):
        value = clean_text(paragraph.get_text(" ", strip=True))
        if len(value) >= _DESCRIPTION_MIN_CHARS:
            return value
    return None


def _modality(value: str | None) -> str | None:
    key = comparison_key(value)
    if not key:
        return None
    in_person, remote = "presencial" in key, ("virtual" in key or "online" in key or "distancia" in key)
    if "semipresencial" in key or "hibrid" in key or (in_person and remote):
        return "Híbrida"
    if in_person:
        return "Presencial"
    if remote:
        return "Virtual"
    return None


def _plan_url(html: str) -> str | None:
    for anchor in _soup(html).find_all("a", href=True):
        if re.search(r"plan[-_ ]?est", anchor["href"], re.I):
            return urljoin(BASE_URL, anchor["href"])
    return None
