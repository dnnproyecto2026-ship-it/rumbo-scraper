"""Deterministic parsers for the public catalogue of the UBA.

The UBA publishes its offer centrally and its detail nowhere: `uba.ar` lists
the thirteen faculties, the address and telephone of each of their campuses and
the careers each one teaches, and then hands off to thirteen faculty sites, one
per CMS, for the plan, the length and the degree awarded. This adapter reads
what the central catalogue states and declares the rest instead of guessing it.

The career list is written with a malformed anchor -- ``<a ... class=""/>Name``
-- so the name that survives parsing is the one in the ``alt`` attribute; the
text inside the list item is the fallback.
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
from rumbo_scraper.normalizers.url import is_official_url

UNIVERSITY = "Universidad de Buenos Aires"
SHORT_NAME = "UBA"
BASE_URL = "https://www.uba.ar"
DOMAIN = "uba.ar"
FACULTIES_URL = f"{BASE_URL}/facultades"
AUTHORITIES_URL = f"{BASE_URL}/autoridades"

# The faculty pages are numbered; the index links every one of them, so the
# spider follows the index instead of walking the range.
FACULTY_PATH = re.compile(r"^/carreras/(\d+)$")

CABA = "Ciudad Autónoma de Buenos Aires"
# The city writes its postal code as C1417DSE; two faculties publish the old
# four-digit form instead, which only reads as a code at the end of the block.
_POSTAL = re.compile(r"\(?\b([A-Z]\d{4}[A-Z]{3})\b\)?")
_OLD_POSTAL = re.compile(r"[,.\s-]\s*(C\s?\d{4})\s*$")
_PHONE = re.compile(r"^[\s(+]*\d[\d\s()/+.-]{6,}$")


@dataclass(frozen=True)
class FacultyRef:
    """A faculty as the index publishes it."""

    id: str
    name: str
    url: str


@dataclass(frozen=True)
class Campus:
    """One address block of a faculty page."""

    name: str
    street: str | None
    number: str | None
    postal_code: str | None
    phone: str | None


def _soup(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style", "noscript"]):
        element.decompose()
    return soup


def discover_faculties(html: str) -> tuple[FacultyRef, ...]:
    """Read the faculties the index links, in the order it lists them."""
    refs: dict[str, FacultyRef] = {}
    for anchor in _soup(html).find_all("a", href=True):
        url = urljoin(BASE_URL, anchor["href"])
        match = FACULTY_PATH.match(url[len(BASE_URL):]) if url.startswith(BASE_URL) else None
        if not match:
            continue
        name = clean_text(anchor.get("alt") or anchor.get_text(" ", strip=True))
        if not name:
            continue
        # The index writes "Facultad de Derecho" in the link and "Derecho" in
        # the heading; the long form is the name of the unit.
        refs.setdefault(match.group(1), FacultyRef(match.group(1), name, url))
    return tuple(refs.values())


def faculty_name(html: str, fallback: str) -> str:
    """The name the faculty page itself prints over its careers."""
    heading = _soup(html).select_one("div.titulo h1")
    name = clean_text(heading.get_text(" ", strip=True)) if heading else ""
    if not name:
        return fallback
    # The page heading drops the "Facultad de" the index carries, and the unit
    # is the same one either way, so the longer published form wins.
    return fallback if comparison_key(name) in comparison_key(fallback) else name


def parse_address(lines: list[str]) -> dict[str, str | None]:
    """Split one address block of a faculty page.

    Every UBA campus is in the city of Buenos Aires and the block writes it in
    full, so the city is the anchor: what precedes it is the street, and the
    postal code is the one token shaped like ``C1417DSE``.
    """
    text = clean_text(" ".join(lines))
    postal = _POSTAL.search(text)
    code = postal.group(1) if postal else None
    head = text[:postal.start()] if postal else text
    city = re.search(r"Ciudad Aut[óo]noma de Buenos Aires|C\.?A\.?B\.?A\.?\b", head, re.I)
    if city:
        head = head[:city.start()]
    head = clean_text(head).strip(" .,-–—")
    if not code:
        old = _OLD_POSTAL.search(head)
        if old:
            code = clean_text(old.group(1)).replace(" ", "")
            head = clean_text(head[:old.start()]).strip(" .,-–—")
    # The number is the first one of the line: what follows it is the building
    # or the campus ("2160, Pabellón III, Ciudad Universitaria"), which belongs
    # to the street and not to the number.
    number = None
    number_match = re.search(r"\b(\d+)\b", head)
    if number_match:
        number = number_match.group(1)
        head = clean_text(
            f"{head[:number_match.start()]} {head[number_match.end():]}"
        ).strip(" .,-–—")
        head = clean_text(re.sub(r"\s+([,;])", r"\1", head)).strip(" .,-–—")
    return {"calle": head or None, "numero": number, "codigo_postal": code}


def parse_campuses(html: str, faculty: str) -> tuple[Campus, ...]:
    """Read the address blocks a faculty page publishes.

    A faculty with two buildings writes one paragraph per building and names
    each one ("Sede SE", "Sede Independencia:"); a faculty with one writes the
    address alone, and that campus takes the faculty's own name.
    """
    block = _soup(html).select_one("div.datos-redes")
    if not block:
        return ()
    campuses: list[Campus] = []
    # The markup nests one paragraph inside another, so only the innermost
    # ones are real blocks; the outer one repeats all of them.
    paragraphs = [p for p in block.find_all("p") if not p.find("p")]
    for paragraph in paragraphs:
        lines = [clean_text(line) for line in paragraph.get_text("\n").split("\n")]
        lines = [line for line in lines if line]
        if not lines:
            continue
        name = faculty
        if len(lines) > 1 and (lines[0].endswith(":") or len(lines[0]) <= 40
                               and comparison_key(lines[0]).startswith("sede")):
            name = clean_text(lines[0]).rstrip(":")
            lines = lines[1:]
        phone = next((line for line in lines if _PHONE.match(line)), None)
        address = parse_address([line for line in lines if not _PHONE.match(line)])
        if not address["calle"]:
            continue
        campuses.append(Campus(name, address["calle"], address["numero"],
                               address["codigo_postal"], phone))
    return tuple(campuses)


def parse_links(html: str) -> dict[str, str]:
    """Read the website and the mail address the faculty page publishes."""
    block = _soup(html).select_one("div.datos-redes")
    links: dict[str, str] = {}
    for anchor in block.find_all("a", href=True) if block else []:
        href = clean_text(anchor["href"])
        if href.lower().startswith("mailto:"):
            value = clean_text(href[7:])
            if "@" in value:
                links.setdefault("email", value)
        elif href.lower().startswith("http"):
            links.setdefault("sitio", href)
    return links


def parse_careers(html: str) -> tuple[tuple[str, str | None], ...]:
    """Read the careers a faculty page lists, with the link it publishes."""
    careers: list[tuple[str, str | None]] = []
    seen: set[str] = set()
    for item in _soup(html).select("ul.lista-simple li"):
        anchor = item.find("a")
        # The anchor is written self-closing, so its text escapes it and the
        # name that survives the parse is the one in the alt attribute.
        name = clean_text(anchor.get("alt") if anchor else "")
        if not name:
            name = clean_text(item.get_text(" ", strip=True))
        if not name or comparison_key(name) in seen:
            continue
        seen.add(comparison_key(name))
        url = clean_text(anchor["href"]) if anchor and anchor.get("href") else None
        careers.append((name, url or None))
    return tuple(careers)


def parse_authorities(html: str) -> list[dict[str, Any]]:
    """Read the authorities of the Rectorado.

    The page writes them in two shapes: the rector and the vice-rector have
    their post in a banner above their name, and everyone else has the post in
    a blue heading followed by the name in an orange one.
    """
    soup = _soup(html)
    headings = soup.find_all(["h1", "h2", "h3", "h4"])
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    section: str | None = None
    for index, heading in enumerate(headings):
        classes = set(heading.get("class") or [])
        text = clean_text(heading.get_text(" ", strip=True))
        if not text or "f-naranja" in classes:
            continue
        if "f-azul" not in classes:
            section = text
            continue
        following = headings[index + 1] if index + 1 < len(headings) else None
        following_classes = set(following.get("class") or []) if following else set()
        if "f-naranja" in following_classes:
            post, name = text, clean_text(following.get_text(" ", strip=True))
        elif section:
            post, name = section, text
        else:
            continue
        identity = (comparison_key(post), comparison_key(name))
        if not name or identity in seen:
            continue
        seen.add(identity)
        rows.append(blank_record(
            "autoridades",
            # The page publishes the authorities of the university, not of a
            # faculty, so the faculty stays empty rather than guessed.
            facultad_nombre=None, carrera=None, cargo=post, tipo="Institucional",
            nombre_autoridad=name,
        ))
    return rows


def build_postgraduates(
    pages: dict[str, str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, str]]]:
    """Read every postgraduate index this adapter covers.

    Returns the contract rows, the detail of each one and the indexes that
    answered with nothing, which is how a page that changed shape is noticed.
    """
    by_faculty: dict[str, dict[str, str]] = {}
    for faculty, url, _, _ in POSTGRADUATE_SOURCES:
        if pages.get(url):
            by_faculty.setdefault(faculty, {})[url] = pages[url]
    chrome = {faculty: chrome_lines(own) for faculty, own in by_faculty.items()}

    rows: list[dict[str, Any]] = []
    details: list[dict[str, Any]] = []
    empty: list[dict[str, str]] = []
    seen: set[str] = set()
    for faculty, url, kind, strategy in POSTGRADUATE_SOURCES:
        html = pages.get(url, "")
        if not html:
            empty.append({"facultad": faculty, "url": url,
                          "motivo": "la página no se pudo descargar"})
            continue
        found = read_postgraduates(html, strategy, kind, chrome.get(faculty, set()))
        if not found:
            empty.append({"facultad": faculty, "url": url,
                          "motivo": "el índice no publicó ningún programa"})
            continue
        for programme in found:
            key = comparison_key(programme["nombre"])
            if key in seen:
                continue
            seen.add(key)
            rows.append(blank_record(
                "posgrados", universidad_nombre=UNIVERSITY, facultad_nombre=faculty,
                nombre_programa=programme["nombre"], tipo_posgrado=programme["tipo"],
                titulo_otorgado=None, sede=None, modalidad=None, duracion_meses=None,
                requiere_tesis_trabajo_final=None, requisito_titulo_previo=None,
                cohorte_inicio=None, costo_total_programa=None, moneda=None,
                descripcion_breve=None, url_oficial=url,
            ))
            details.append({"facultad": faculty, "nombre": programme["nombre"],
                            "tipo": programme["tipo"], "fuente_url": url})
    return rows, details, empty


def build_dataset(
    faculties: tuple[FacultyRef, ...],
    pages: dict[str, str],
    authorities_html: str = "",
    errors: list[dict[str, str]] | None = None,
    postgraduate_pages: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Assemble the UBA dataset from the central catalogue."""
    data: dict[str, list[dict[str, Any]]] = {section: [] for section in SECTION_FIELDS}
    data["universidades"] = [blank_record(
        "universidades", nombre_oficial=UNIVERSITY, nombre_corto=SHORT_NAME,
        tipo_gestion="Estatal", anio_fundacion=1821, sitio_web=BASE_URL,
    )]
    data["localidades"] = [blank_record(
        "localidades", nombre_localidad=CABA, provincia="CABA",
    )]

    details: list[dict[str, Any]] = []
    resources: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    misspelled: list[str] = []
    shared_campus = 0
    for ref in faculties:
        html = pages.get(ref.url, "")
        if not html:
            excluded.append({"facultad": ref.name, "url": ref.url,
                             "motivo": "la página no se pudo descargar"})
            continue
        name = faculty_name(html, ref.name)
        # One of the thirteen is published as "Faculta de Psicología". The
        # name is stored as the university writes it and the deviation is
        # reported, because correcting a source is still changing it.
        if not comparison_key(name).startswith("facultad"):
            misspelled.append(name)
        campuses = parse_campuses(html, name)
        careers = parse_careers(html)
        links = parse_links(html)
        data["facultades"].append(blank_record(
            "facultades", universidad_nombre=UNIVERSITY, nombre_facultad=name,
            tipo_unidad="Facultad",
            sede=campuses[0].name if len(campuses) == 1 else None,
        ))
        for campus in campuses:
            data["sedes"].append(blank_record(
                "sedes", universidad_nombre=UNIVERSITY, nombre_sede=campus.name,
                localidad=CABA, calle=campus.street, numero=campus.number,
                tipo_sede="Campus",
            ))
            if campus.phone:
                data["redes_contacto"].append(blank_record(
                    "redes_contacto", universidad_nombre=UNIVERSITY,
                    facultad_nombre=name, canal="Teléfono",
                    usuario_o_direccion=campus.phone,
                ))
        for channel, key in (("Sitio Web", "sitio"), ("Email", "email")):
            if links.get(key):
                data["redes_contacto"].append(blank_record(
                    "redes_contacto", universidad_nombre=UNIVERSITY,
                    facultad_nombre=name, canal=channel,
                    usuario_o_direccion=links[key],
                ))
        # A faculty with one published address teaches its careers there; one
        # with two does not say which, so the campus stays empty.
        campus_name = campuses[0].name if len(campuses) == 1 else None
        if len(campuses) > 1:
            shared_campus += len(careers)
        for career, url in careers:
            data["carreras"].append(blank_record(
                "carreras", universidad_nombre=UNIVERSITY, facultad_nombre=name,
                nombre_carrera=career, denominacion_canonica=career,
                nivel="Grado", titulo_otorgado=None, tiene_titulo_intermedio=None,
                duracion_anios=None, descripcion_breve=None,
                cantidad_materias_total=None,
            ))
            data["ofertas"].append(blank_record(
                "ofertas", universidad_nombre=UNIVERSITY, facultad_nombre=name,
                carrera_nombre=career, sede=campus_name, modalidad=None,
                regimen_ingreso=None, coneau_resolucion=None,
                coneau_vigencia_hasta=None, tiene_pasantias=None,
                tiene_bolsa_trabajo=None,
                # The faculty's own link may leave uba.ar, so the evidence is
                # the central page that published it and the link is a resource.
                url_oficial=ref.url,
            ))
            if url:
                resources.append({
                    "entidad_tipo": "carrera", "entidad_nombre": career,
                    "tipo_recurso": "pagina", "titulo": f"Página de {career}",
                    "url": url, "fuente_url": ref.url,
                    "en_dominio_oficial": is_official_url(url, DOMAIN,
                                                          require_https=False),
                })
        details.append({
            "id": ref.id, "facultad": name, "url": ref.url,
            "sedes": [campus.name for campus in campuses],
            "carreras": [career for career, _ in careers],
        })

    data["autoridades"] = parse_authorities(authorities_html)
    programmes, programme_details, empty_indexes = build_postgraduates(
        postgraduate_pages or {}
    )
    data["posgrados"] = programmes

    missing = [section for section, rows in data.items() if not rows]
    return {
        "universidad": UNIVERSITY,
        "fuente_principal": FACULTIES_URL,
        "extraido_en": datetime.now(timezone.utc).isoformat(),
        "metodo": "HTML público del catálogo central; sin IA",
        "datos": data,
        "recursos_publicos": resources,
        "detalle_facultades": details,
        "detalle_posgrados": programme_details,
        "directorio_academico": {"personas": [], "roles_academicos": []},
        "control_calidad": {
            "secciones_vacias": missing,
            "secciones_sin_fuente_publica": {
                # The central catalogue names the careers and links to the
                # faculty that teaches each one; everything about the career
                # itself lives on thirteen different faculty sites.
                "materias": "el catálogo central no publica los planes de estudio",
                "carreras.titulo_otorgado": "el catálogo central no publica el "
                                            "título que expide cada carrera",
                "carreras.duracion_anios": "el catálogo central no publica la "
                                           "duración de cada carrera",
                "carreras.cantidad_materias_total": "el catálogo central no "
                                                    "publica el plan de estudios",
                "aranceles": "la universidad es pública y no publica aranceles",
                "turnos_anio": "el catálogo central no publica horarios",
                "ofertas_ciclo": "el catálogo central no publica ciclos",
                "areas_tematicas": "el catálogo central no agrupa por área",
                "actividades": "el catálogo central no publica prácticas",
                "becas": "las becas se publican fuera del catálogo",
                "servicios_estudiantiles": "no hay catálogo central de servicios",
                "actividades_extracurriculares": "no hay catálogo central",
                "alojamiento": "no hay catálogo central",
                "programas_internacionales": "no hay catálogo central",
                "convenios_intercambio": "no hay catálogo central",
            },
            "facultades_descubiertas": len(faculties),
            "facultades_excluidas": excluded,
            "carreras_sin_sede_publicada": shared_campus,
            "posgrados_por_facultad_sin_leer": POSTGRADUATES_NOT_READ,
            "indices_de_posgrado_vacios": empty_indexes,
            "nombres_de_facultad_fuera_de_forma": misspelled,
            "errores_descarga": errors or [],
            "nota": "Los valores ausentes permanecen nulos; no se inventan datos.",
        },
    }


# ---------------------------------------------------------------------------
# Postgraduate programmes
# ---------------------------------------------------------------------------
#
# The UBA states that it offers more than 660 postgraduate programmes and
# publishes none of them centrally: each faculty publishes its own list, on its
# own site, in one of three shapes. The reader below has one strategy per
# shape, and each source below declares which one it is written in, so a page
# that changes shape fails loudly instead of returning a shorter list.

POSTGRADUATE_KINDS: tuple[tuple[str, str], ...] = (
    ("posdoctorado", "Posdoctorado"),
    ("doctorado", "Doctorado"),
    ("maestria", "Maestría"),
    ("magister", "Maestría"),
    ("especializacion", "Especialización"),
    ("especialista", "Especialización"),
    ("programa de actualizacion", "Programa de Actualización"),
    ("actualizacion", "Programa de Actualización"),
    ("diplomatura", "Diplomatura"),
)

# The heading that opens a list of programmes of one kind.
_KIND_HEADING = re.compile(
    r"^(carreras?\s+de\s+|programas?\s+de\s+|listado\s+de\s+)?"
    r"(especializaci[oó]n(es)?|maestr[ií]a(s)?|doctorado(s)?|diplomatura(s)?|"
    r"actualizaci[oó]n(es)?|posdoctorado(s)?)\b"
)
# Lines that belong to the page and never to a programme.
_NOT_A_PROGRAMME = re.compile(
    r"^(requiere|contactarse|solicitar|res\b|resoluci|coneau|ver m|leer m|"
    r"inscrip|requisit|descarg|contacto|m[áa]s inf|aranc|reglamento|normativa|"
    r"comments|\(ex |autoridades|cronograma|calendario|defensa|home|volver|"
    r"compartir|imprimir|informaci[óo]n|premios|novedades|agenda|biblioteca|"
    r"institucional|buscador|pr[óo]xima|cursos? en|plan de estudio|"
    r"modalidad|presentaci[óo]n|estructura|convocatoria|actividades)",
    re.I,
)


def postgraduate_kind(name: str) -> str | None:
    """The kind a programme's own name states, if it states one."""
    key = comparison_key(name)
    for token, label in POSTGRADUATE_KINDS:
        if re.search(rf"\b{token}", key):
            return label
    return None


def _candidate(text: str) -> str:
    return clean_text(text).strip(" .·—–-")


# "Especializaciones de Filosofía y Letras" is the title of the page, not a
# programme: the plural of a kind opens a section and never a name.
_SECTION_TITLE = re.compile(
    r"^(especializaciones|maestr[ií]as|doctorados|diplomaturas|posdoctorados|"
    r"programas|otras?|otros?)\b"
)


def _usable(name: str) -> bool:
    return (10 <= len(name) <= 120 and "@" not in name
            and name[:1].isalpha()
            and not _NOT_A_PROGRAMME.match(name)
            and not _SECTION_TITLE.match(comparison_key(name))
            and bool(re.search(r"[a-záéíóúñ]", name)))


def read_list_page(html: str) -> list[str]:
    """Read a page that opens with the kind and then lists the programmes.

    Used by the faculties that write "Maestrías" as a heading and the names
    below it, each one its own list item or link.
    """
    soup = _soup(html)
    for element in soup(["nav", "footer", "header", "aside"]):
        element.decompose()
    for heading in soup.find_all(["h1", "h2", "h3", "h4", "strong", "b"]):
        opening = _candidate(heading.get_text(" ", strip=True))
        if not _KIND_HEADING.match(comparison_key(opening)):
            continue
        names: list[str] = []
        # Everything that follows the heading, until the next one opens a
        # different section.
        for node in heading.find_all_next():
            if node.name in ("h1", "h2", "h3", "h4") and node is not heading:
                other = _candidate(node.get_text(" ", strip=True))
                if other and other != opening:
                    break
            if node.name in ("li", "a"):
                name = _candidate(node.get_text(" ", strip=True))
                if _usable(name) and name != opening and name not in names:
                    names.append(name)
        if len(names) > 1:
            return names
    return []


def read_heading_page(html: str) -> list[str]:
    """Read a page where every programme is a heading of its own."""
    soup = _soup(html)
    for element in soup(["nav", "footer", "header", "aside"]):
        element.decompose()
    names: list[str] = []
    for heading in soup.find_all(["h1", "h2", "h3", "h4"]):
        name = _candidate(heading.get_text(" ", strip=True))
        if not _usable(name) or not postgraduate_kind(name):
            continue
        if _KIND_HEADING.fullmatch(comparison_key(name)) or name in names:
            continue
        names.append(name)
    return names


def read_paragraph_page(html: str, chrome: set[str]) -> list[str]:
    """Read a page that writes the names as plain text under the heading.

    There is no markup separating a name from the sentence beside it, so the
    lines this faculty repeats on its other pages are removed as furniture and
    what is left is the list.
    """
    soup = _soup(html)
    for element in soup(["nav", "footer", "header", "aside"]):
        element.decompose()
    names: list[str] = []
    for raw in soup.get_text("\n").split("\n"):
        name = _candidate(raw)
        if name in chrome or not _usable(name) or name in names:
            continue
        if _KIND_HEADING.fullmatch(comparison_key(name)) or "|" in name:
            continue
        if re.search(r"\d{4}|\bdel?\s+\d", name):
            continue
        names.append(name)
    return names


# Every postgraduate index this adapter reads, with the faculty that publishes
# it, the kind it announces and the shape it is written in. The faculties that
# are missing from this table publish their offer in a form this reader does
# not cover yet, and are reported instead of being left silent.
POSTGRADUATE_SOURCES: tuple[tuple[str, str, str, str], ...] = (
    ("Facultad de Agronomía", "https://epg.agro.uba.ar/doctorados/",
     "Doctorado", "lista"),
    ("Facultad de Agronomía",
     "https://epg.agro.uba.ar/carreras-ofrecidas-en-la-epg-2/carreras-de-maestria/",
     "Maestría", "lista"),
    ("Facultad de Agronomía", "https://epg.agro.uba.ar/carreras-de-especializacion/",
     "Especialización", "lista"),
    ("Facultad de Arquitectura, Diseño y Urbanismo",
     "https://www.fadu.uba.ar/maestrias/", "Maestría", "parrafos"),
    ("Facultad de Arquitectura, Diseño y Urbanismo",
     "https://www.fadu.uba.ar/posgrados-carreras-de-especializacion/",
     "Especialización", "parrafos"),
    ("Facultad de Arquitectura, Diseño y Urbanismo",
     "https://www.fadu.uba.ar/programas-actualizacion/",
     "Programa de Actualización", "parrafos"),
    ("Facultad de Ciencias Exactas y Naturales",
     "https://exactas.uba.ar/ensenanza/carreras-de-posgrado/maestrias/",
     "Maestría", "titulos"),
    ("Facultad de Ciencias Exactas y Naturales",
     "https://exactas.uba.ar/ensenanza/carreras-de-posgrado/especializaciones/",
     "Especialización", "titulos"),
    ("Facultad de Ciencias Exactas y Naturales",
     "https://exactas.uba.ar/ensenanza/diplomaturas/", "Diplomatura", "titulos"),
    ("Facultad de Filosofía y Letras", "https://posgrado.filo.uba.ar/maestrias",
     "Maestría", "lista"),
    ("Facultad de Filosofía y Letras",
     "https://posgrado.filo.uba.ar/carreras-de-especializaci%C3%B3n",
     "Especialización", "parrafos"),
    ("Facultad de Filosofía y Letras",
     "https://posgrado.filo.uba.ar/programas-de-actualizaci%C3%B3n",
     "Programa de Actualización", "lista"),
    ("Facultad de Ingeniería", "https://www.fi.uba.ar/posgrado/maestrias",
     "Maestría", "lista"),
    ("Facultad de Ingeniería",
     "https://www.fi.uba.ar/posgrado/carreras-de-especializacion",
     "Especialización", "lista"),
    ("Facultad de Ingeniería", "https://www.fi.uba.ar/posgrado/diplomaturas",
     "Diplomatura", "lista"),
)

POSTGRADUATE_URLS = tuple(dict.fromkeys(url for _, url, _, _ in POSTGRADUATE_SOURCES))

# The faculties whose postgraduate offer is published in a form this reader
# does not cover, with what stands in the way of reading it.
POSTGRADUATES_NOT_READ = {
    "Facultad de Ciencias Económicas": "la escuela de posgrado publica su oferta "
                                       "por área temática, sin un listado de programas",
    "Facultad de Ciencias Sociales": "el listado está dentro de una página que "
                                     "mezcla la oferta con el calendario académico",
    "Facultad de Ciencias Veterinarias": "la oferta está en anclas de una sola "
                                         "página, sin un índice por tipo",
    "Facultad de Derecho": "la oferta está detrás de enlaces 'Más información' "
                           "que no publican el listado",
    "Facultad de Farmacia y Bioquímica": "una sola página mezcla los cuatro tipos "
                                         "sin separarlos",
    "Facultad de Ciencias Médicas": "la oferta se publica en subpáginas por "
                                    "especialidad, sin un índice",
    "Facultad de Odontología": "la oferta está en anclas de una sola página",
    "Facultad de Psicología": "la oferta se publica en un visor por año lectivo",
}


def chrome_lines(pages: dict[str, str]) -> set[str]:
    """The lines a faculty repeats on its own pages, which are furniture."""
    counts: dict[str, int] = {}
    for html in pages.values():
        soup = _soup(html)
        for element in soup(["nav", "footer", "header", "aside"]):
            element.decompose()
        for line in {_candidate(raw) for raw in soup.get_text("\n").split("\n")}:
            if line:
                counts[line] = counts.get(line, 0) + 1
    return {line for line, count in counts.items() if count >= 2}


STRATEGIES = {"lista": "read_list_page", "titulos": "read_heading_page",
              "parrafos": "read_paragraph_page"}


def read_postgraduates(
    html: str, strategy: str, kind: str, chrome: set[str] | None = None
) -> list[dict[str, str]]:
    """Read one faculty page and name every programme it publishes.

    A name that already states its kind keeps it; a page that lists bare names
    lends them the kind it announces, the same way the UTN catalogue does.
    """
    if strategy == "lista":
        names = read_list_page(html)
    elif strategy == "titulos":
        names = read_heading_page(html)
    elif strategy == "parrafos":
        names = read_paragraph_page(html, chrome or set())
    else:
        raise ValueError(f"Estrategia desconocida: {strategy!r}")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for name in names:
        stated = postgraduate_kind(name)
        full = name if stated else f"{kind} en {name}"
        if comparison_key(full) in seen:
            continue
        seen.add(comparison_key(full))
        rows.append({"nombre": full, "tipo": stated or kind})
    return rows
