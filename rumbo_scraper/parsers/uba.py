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
    career_pages: dict[str, str] | None = None,
    plan_pages: dict[str, str] | None = None,
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

    career_pages = career_pages or {}
    plan_pages = plan_pages or {}
    details: list[dict[str, Any]] = []
    resources: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    misspelled: list[str] = []
    without_plan: list[dict[str, str]] = []
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
            # The faculty page is where the plan of the career lives, if the
            # faculty publishes one at all.
            # The page of the career is where the faculty links its plan. The
            # document is recorded as a public resource; its subjects are not
            # read here, because a generic reading of thirteen faculties'
            # documents mixes real subjects with fragments of their prose, and
            # a wrong subject is worse than a missing one.
            page = career_pages.get(url or "", "")
            plan_url = plan_document_url(page, url or "") if page else None
            # A plan published as a table of a page can be read; the ones
            # published as a resolution or a diagram cannot, and are linked.
            plan_page = plan_pages.get(plan_url or "", "")
            if plan_page:
                plan = read_plan_tables(plan_page, career)
                if plan["materias"]:
                    data["materias"].extend(plan["materias"])
                    data["carreras"][-1]["cantidad_materias_total"] = len(plan["materias"])
                else:
                    without_plan.append({"carrera": career, "url": plan_url,
                                         "motivo": plan["motivo"]})
            if plan_url:
                resources.append({
                    "entidad_tipo": "carrera", "entidad_nombre": career,
                    "tipo_recurso": "documento",
                    "titulo": f"Plan de estudios de {career}",
                    "url": plan_url, "fuente_url": url,
                    "en_dominio_oficial": True,
                })
            else:
                without_plan.append({"carrera": career, "url": url,
                                     "motivo": "la facultad no publica el plan "
                                               "en la página de la carrera"})
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
                # The plan of each career is published by its own faculty, as a
                # document of its own layout. They are linked one by one in
                # recursos_publicos; reading them needs a reader per faculty,
                # the way the postgraduate indexes did.
                "materias": "se leen los planes publicados como tabla; los "
                            "que son una resolución o un diagrama se enlazan",
                "carreras.cantidad_materias_total": "depende de que la facultad "
                                                    "publique el plan como tabla",
                # The central catalogue names the careers and links to the
                # faculty that teaches each one; everything about the career
                # itself lives on thirteen different faculty sites.
                "carreras.titulo_otorgado": "el catálogo central no publica el "
                                            "título que expide cada carrera",
                "carreras.duracion_anios": "el catálogo central no publica la "
                                           "duración de cada carrera",
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
            "carreras_sin_plan_publicado": without_plan,
            "posgrados_por_facultad_sin_leer": POSTGRADUATES_NOT_READ,
            "posgrados_parciales_por_facultad": POSTGRADUATE_PARTS_NOT_READ,
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
    """One line as the page prints it, without the marker that opens a panel."""
    return clean_text(re.sub(r"\s*\[\+\]\s*$", "", clean_text(text))).strip(" .·—–-")


# "Especializaciones de Filosofía y Letras" is the title of the page, not a
# programme: the plural of a kind opens a section and never a name.
_SECTION_TITLE = re.compile(
    r"^(especializaciones|maestr[ií]as|doctorados|diplomaturas|posdoctorados|"
    r"programas|otras?|otros?)\b"
)


# A line the extractor cut in half ends where the next one begins: "Maestría
# con título" is the first half of "...intermedio de Especialista".
_CUT_OFF = re.compile(
    r"\b(con|de|del|en|para|por|y|e|la|el|los|las|un|una|titulo|t[ií]tulo|"
    r"intermedio|sobre|entre)$", re.I
)


def _usable(name: str) -> bool:
    # A pipe joins a person to their post -- "Emanuel Porcelli | Subsecretario
    # de Maestrías" -- and never appears inside the name of a programme.
    return (10 <= len(name) <= 120 and "@" not in name and "|" not in name
            and not _CUT_OFF.search(comparison_key(name))
            and name[:1].isalpha() and not name.endswith(":")
            and not _NOT_A_PROGRAMME.match(name)
            and not _SECTION_TITLE.match(comparison_key(name))
            and bool(re.search(r"[a-záéíóúñ]", name)))


def read_list_page(html: str, kind: str | None = None) -> list[str]:
    """Read a page that opens with the kind and then lists the programmes.

    Used by the faculties that write "Maestrías" as a heading and the names
    below it, each one its own list item or link. A page with one section per
    kind is read once per kind, so the heading that opens the block has to be
    the one that announces the kind being asked for.
    """
    soup = _soup(html)
    for element in soup(["nav", "footer", "header", "aside"]):
        element.decompose()
    wanted = comparison_key(kind) if kind else None
    for heading in soup.find_all(["h1", "h2", "h3", "h4", "strong", "b"]):
        opening = _candidate(heading.get_text(" ", strip=True))
        if not _KIND_HEADING.match(comparison_key(opening)):
            continue
        if wanted and not re.match(rf"^\W*(carreras?|programas?)?\s*(de\s+)?{wanted[:8]}",
                                   comparison_key(opening)):
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
        if names:
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


def _states_several_kinds(name: str) -> bool:
    """A line that names two programmes is a sentence, not a programme.

    It reads either as two kinds ("Doctorado y Posdoctorado") or as the same
    one twice ("Doctorado, área Farmacia y el Doctorado Binacional").
    """
    key = comparison_key(name)
    labels = set()
    occurrences = 0
    for token, label in POSTGRADUATE_KINDS:
        found = len(re.findall(rf"\b{token}", key))
        if found:
            labels.add(label)
            occurrences += found
    return len(labels) > 1 or occurrences > 1


def read_mixed_page(html: str) -> list[str]:
    """Read a page that lists every kind together without separating them.

    Three faculties publish one page for their whole offer, so the kind cannot
    come from a heading: only the entries that name their own kind are read,
    and the headings that announce a section are left out.

    Only the footer is dropped. One faculty puts its whole catalogue inside a
    ``<nav>`` -- the tabs are the sections -- so removing the furniture by tag
    would remove the offer with it; here the name is the filter.
    """
    soup = _soup(html)
    for element in soup(["footer"]):
        element.decompose()
    names: list[str] = []
    for node in soup.find_all(["li", "a", "h2", "h3", "h4", "p", "strong", "td"]):
        name = _candidate(node.get_text(" ", strip=True))
        if not _usable(name) or not postgraduate_kind(name) or name in names:
            continue
        if _KIND_HEADING.fullmatch(comparison_key(name)) or _states_several_kinds(name):
            continue
        names.append(name)
    return names


def read_panel(html: str, anchor: str) -> list[str]:
    """Read the panel of a page whose sections are tabs.

    One faculty publishes its whole offer on one page and opens each kind in
    its own tab; the fragment of the source URL names the panel, so the kind
    comes from which tab the names are in.
    """
    element = _soup(html).find(id=anchor)
    if element is None:
        return []
    names: list[str] = []
    for node in element.find_all(["li", "a"]):
        name = _candidate(node.get_text(" ", strip=True))
        if not _usable(name) or name in names:
            continue
        if _KIND_HEADING.fullmatch(comparison_key(name)) or _states_several_kinds(name):
            continue
        names.append(name)
    return names


def read_selected(html: str, selector: str) -> list[str]:
    """Read the names a page keeps in one element of its own markup.

    Two faculties write a paragraph of directors and contacts under every
    programme, so no rule over the text can tell a name from a person. Their
    markup does say it, and the source declares which element holds the name.
    """
    names: list[str] = []
    for node in _soup(html).select(selector):
        name = _candidate(node.get_text(" ", strip=True))
        if not _usable(name) or name in names:
            continue
        if _KIND_HEADING.fullmatch(comparison_key(name)) or _states_several_kinds(name):
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
        if _KIND_HEADING.fullmatch(comparison_key(name)):
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
    ("Facultad de Ciencias Económicas",
     "https://economicas.uba.ar/posgrado/oferta-academica/categorias/",
     "Maestría", "lista"),
    ("Facultad de Ciencias Económicas",
     "https://economicas.uba.ar/posgrado/oferta-academica/categorias/",
     "Especialización", "lista"),
    ("Facultad de Ciencias Económicas",
     "https://economicas.uba.ar/posgrado/oferta-academica/categorias/",
     "Diplomatura", "lista"),
    ("Facultad de Ciencias Sociales",
     "https://www.sociales.uba.ar/posgrados/maestriasyespecializaciones/",
     "Maestría", "mezcla"),
    ("Facultad de Ciencias Veterinarias",
     "https://www.fvet.uba.ar/?q=escuelaGraduados", "Maestría", "mezcla"),
    ("Facultad de Derecho",
     "https://www.derecho.uba.ar/academica/posgrados/maestrias.php",
     "Maestría", "selector:div.carrera h3"),
    ("Facultad de Derecho",
     "https://www.derecho.uba.ar/academica/posgrados/carr_especializacion.php",
     "Especialización", "selector:div.carrera h3"),
    ("Facultad de Farmacia y Bioquímica",
     "https://www.ffyb.uba.ar/secretaria-de-posgrado/", "Especialización", "mezcla"),
    ("Facultad de Odontología", "https://posgrado.odontologia.uba.ar/",
     "Diplomatura", "panel:curso-0"),
    ("Facultad de Odontología", "https://posgrado.odontologia.uba.ar/",
     "Especialización", "panel:curso-1"),
    ("Facultad de Odontología", "https://posgrado.odontologia.uba.ar/",
     "Maestría", "panel:curso-2"),
    ("Facultad de Derecho",
     "https://www.derecho.uba.ar/academica/posgrados/prog_actualizacion.php",
     "Programa de Actualización", "selector:div.contenido_pagina-col2 > h3"),
    ("Facultad de Ciencias Médicas",
     "https://www.fmed.uba.ar/carreras-de-especialistas/ofertas-de-carreras-de-especializacion",
     "Especialización", "selector:div.field--name-field-titulo"),
    ("Facultad de Ciencias Médicas",
     "https://www.fmed.uba.ar/index.php/maestrias/oferta-de-maestrias",
     "Maestría", "selector:div.field--name-field-titulo"),
    ("Faculta de Psicología", "https://www.psi.uba.ar/posgrado.php?var=posgrado2026_2/oferta.php", "Maestría", "panel:Maestrias"),
    ("Faculta de Psicología", "https://www.psi.uba.ar/posgrado.php?var=posgrado2026_2/oferta.php", "Especialización", "panel:Carreras"),
    ("Faculta de Psicología", "https://www.psi.uba.ar/posgrado.php?var=posgrado2026_2/oferta.php", "Programa de Actualización", "panel:Programas"),
)

POSTGRADUATE_URLS = tuple(dict.fromkeys(url for _, url, _, _ in POSTGRADUATE_SOURCES))

# The faculties whose postgraduate offer is published in a form this reader
# does not cover, with what stands in the way of reading it.
# Every faculty of the university is read; this stays as the place to declare
# one that stops being readable.
POSTGRADUATES_NOT_READ: dict[str, str] = {}

# Sections of a faculty already covered above that publish a kind in a form
# this reader does not cover; the faculty is read, this part of it is not.
POSTGRADUATE_PARTS_NOT_READ = {
    "Facultad de Derecho": "el doctorado se describe en prosa y la facultad "
                           "tiene uno solo, sin un nombre propio que leer",
    "Facultad de Ciencias Sociales": "los programas de actualización están "
                                     "mezclados con el calendario académico",
    "Facultad de Ciencias Económicas": "los cursos y los programas ejecutivos no "
                                       "son títulos del contrato",
    "Facultad de Ciencias Médicas": "los doctorados y los cursos se describen en "
                                    "prosa, sin un listado",
    "Faculta de Psicología": "el doctorado y el posdoctorado se publican como "
                             "reglamentos y aranceles, sin un nombre de programa",
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
              "parrafos": "read_paragraph_page", "mezcla": "read_mixed_page",
              "panel": "read_panel", "selector": "read_selected"}


def read_postgraduates(
    html: str, strategy: str, kind: str, chrome: set[str] | None = None
) -> list[dict[str, str]]:
    """Read one faculty page and name every programme it publishes.

    A name that already states its kind keeps it; a page that lists bare names
    lends them the kind it announces, the same way the UTN catalogue does.
    """
    if strategy == "lista":
        names = read_list_page(html, kind)
    elif strategy == "titulos":
        names = read_heading_page(html)
    elif strategy == "parrafos":
        names = read_paragraph_page(html, chrome or set())
    elif strategy == "mezcla":
        names = read_mixed_page(html)
    elif strategy.startswith("panel:"):
        names = read_panel(html, strategy.split(":", 1)[1])
    elif strategy.startswith("selector:"):
        names = read_selected(html, strategy.split(":", 1)[1])
    else:
        raise ValueError(f"Estrategia desconocida: {strategy!r}")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for name in names:
        stated = postgraduate_kind(name)
        if stated:
            full = name
        elif re.match(r"(?i)^(en|de|del)\s", name):
            # One faculty writes the names as the tail of its own heading:
            # "en Biología Molecular Médica" under "Oferta de Maestrías".
            full = f"{kind} {name}"
        else:
            full = f"{kind} en {name}"
        if comparison_key(full) in seen:
            continue
        seen.add(comparison_key(full))
        rows.append({"nombre": full, "tipo": stated or kind})
    return rows


# ---------------------------------------------------------------------------
# Study plans
# ---------------------------------------------------------------------------
#
# The central catalogue links each career to the site of the faculty that
# teaches it, and eighty-one of those pages publish a study plan. They are the
# only place the UBA states what a career is made of.

_PLAN_LABEL = re.compile(r"plan\s+de\s+estudio", re.I)
# A line of the plan that describes the table instead of naming a subject.
_PLAN_NOISE = re.compile(
    r"^(cod\s*\d|c[óo]d\.?\s*\d|[A-Z]{1,3}\s+Final\b|total|carga|correlativ)", re.I
)
# What the table calls its columns is not one of its rows.
_COLUMN_LABEL = frozenset({
    "asignatura", "asignaturas", "materia", "materias", "nombre", "codigo",
    "cod", "plan", "nuevo plan", "plan nuevo", "plan anterior", "horas",
    "carga horaria", "regimen", "cuatrimestre", "ciclo", "anio", "ano",
    "correlativas", "correlatividades", "observaciones", "creditos",
    "plan 1993", "plan 2016", "plan 2017", "plan 2023",
    "espacio curricular", "espacios curriculares", "denominacion",
})


def plan_document_url(html: str, page_url: str) -> str | None:
    """Find the plan the faculty links from the page of a career."""
    for anchor in _soup(html).find_all("a", href=True):
        if not _PLAN_LABEL.search(anchor.get_text(" ", strip=True)):
            continue
        url = urljoin(page_url, clean_text(anchor["href"]))
        if is_official_url(url, DOMAIN, require_https=False):
            return url
    return None


def clean_subject(name: str) -> str | None:
    """Drop what the plan table says about a subject but is not its name.

    The faculties print the subject's code in the same cell as its name and
    a legend of the table in the same column, so both arrive joined to it.
    """
    value = clean_text(re.sub(r"^\s*(cod|c[óo]d\.?)\s*\d+\s*", "", name, flags=re.I))
    # A lone capital at the end is the legend of the table ("F" for final),
    # except when it is the roman numeral that numbers the subject: dropping
    # it would turn "Anatomía I" into "Anatomía".
    value = clean_text(re.sub(r"\s+[A-HJ-UWYZ]\s*$", "", value))
    if len(value) < 4 or _PLAN_NOISE.match(value):
        return None
    if comparison_key(value) in _COLUMN_LABEL:
        return None
    return value


# A plan is kept only when its reading looks like a plan. The thirteen
# faculties publish documents of every quality, and a table the extractor
# scrambles yields lines like "CBC aprobado" or three subjects run together;
# those are not worth storing next to the ones that read cleanly.
MIN_SUBJECTS = 8
MIN_WITH_YEAR = 0.7
MAX_NAME_LENGTH = 70


def plan_is_sound(subjects: list[dict[str, Any]]) -> tuple[bool, str]:
    """Say whether a reading of a plan can be trusted, and why not."""
    if len(subjects) < MIN_SUBJECTS:
        return False, "el documento publicó menos materias que las de un plan"
    with_year = sum(1 for row in subjects if row["anio_cursada"])
    if with_year < MIN_WITH_YEAR * len(subjects):
        return False, "el documento no conserva el año de la mayoría de las materias"
    long_names = sum(1 for row in subjects
                     if len(str(row["nombre_materia"])) > MAX_NAME_LENGTH)
    if long_names > len(subjects) / 5:
        # Names this long are several subjects the extractor ran together.
        return False, "el texto extraído une varias materias en una línea"
    return True, ""


def read_plan(document: bytes, career: str) -> dict[str, Any]:
    """Read the plan of one career out of the document the faculty publishes."""
    from rumbo_scraper.parsers.plan_documents import parse_plan_pdf

    result = parse_plan_pdf(document, career, UNIVERSITY)
    subjects = []
    for row in result["materias"]:
        name = clean_subject(str(row["nombre_materia"]))
        if not name:
            result["descartadas"] = result.get("descartadas", 0) + 1
            continue
        subjects.append({**row, "nombre_materia": name})
    sound, reason = plan_is_sound(subjects)
    result["materias"] = subjects if sound else []
    result["motivo"] = result["motivo"] or (None if sound else reason)
    return result


# A table of a plan states one subject per row. A calendar states one day per
# cell, and several faculties put one in the sidebar of the same page.
_WEEKDAY_HEADER = re.compile(r"^[dlmjvs]{1,2}$", re.I)
_YEAR_HEADING = re.compile(
    r"(primer|segundo|tercer|cuarto|quinto|sexto|s[ée]ptimo)\s+a[ñn]o"
    r"|\b([1-7])\s*[°ºa]?\s*a[ñn]o\b", re.I
)
_YEAR_WORDS = {"primer": 1, "segundo": 2, "tercer": 3, "cuarto": 4,
               "quinto": 5, "sexto": 6, "septimo": 7}
MIN_PLAN_ROWS = 6


def _is_calendar(rows: list[list[str]]) -> bool:
    """A month has seven columns of one letter and a body of bare numbers."""
    header = rows[0] if rows else []
    if len(header) == 7 and all(_WEEKDAY_HEADER.match(cell or "x") for cell in header):
        return True
    cells = [cell for row in rows for cell in row if cell]
    numeric = sum(1 for cell in cells if cell.isdigit())
    return bool(cells) and numeric > len(cells) * 0.7


# A cell that lists what has to be approved first is a requirement, not a
# name: it enumerates other subjects, or it says so in a sentence.
_A_REQUIREMENT = re.compile(
    r";|\b(tener|haber|aprobad|cursad|regulariz|requisito|elegir|incluyendo)", re.I
)


def _looks_like_a_name(value: str) -> bool:
    return (6 <= len(value) <= 70 and bool(re.search(r"[^\W\d_]{4}", value))
            and not _A_REQUIREMENT.search(value))


def _subject_column(rows: list[list[str]]) -> int | None:
    """The column that holds the names of the subjects.

    The wordiest column of a plan is usually the one listing what has to be
    approved before each subject, so the column is chosen by how many of its
    cells read like a name and not by how much text they hold.
    """
    width = max((len(row) for row in rows), default=0)
    best, best_score = None, 0.0
    for index in range(width):
        values = [row[index] for row in rows if index < len(row) and row[index]]
        if len(values) < MIN_PLAN_ROWS:
            continue
        named = {value for value in values if _looks_like_a_name(value)}
        score = len(named) / len(values)
        if score > best_score and len(named) >= MIN_PLAN_ROWS:
            best, best_score = index, score
    return best if best_score >= 0.6 else None


def _year_above(table: Any) -> int | None:
    """The year the page announces above the table, if it announces one."""
    for node in table.find_all_previous(["h1", "h2", "h3", "h4", "caption", "strong"]):
        match = _YEAR_HEADING.search(clean_text(node.get_text(" ", strip=True)))
        if not match:
            continue
        word = comparison_key(match.group(1) or "")
        return _YEAR_WORDS.get(word) or (int(match.group(2)) if match.group(2) else None)
    return None


def read_plan_tables(html: str, career: str) -> dict[str, Any]:
    """Read a plan the faculty publishes as a table of its own page.

    Twenty of the eighty-one plans are real tables, one subject per row, and a
    table is worth reading where a scrambled PDF is not: the columns survive.
    """
    soup = _soup(html)
    for element in soup(["nav", "footer", "header", "aside"]):
        element.decompose()
    subjects: list[dict[str, Any]] = []
    seen: set[str] = set()
    for table in soup.find_all("table"):
        rows = [[clean_text(cell.get_text(" ", strip=True))
                 for cell in row.find_all(["td", "th"])]
                for row in table.find_all("tr")]
        rows = [row for row in rows if any(row)]
        if len(rows) < MIN_PLAN_ROWS or _is_calendar(rows):
            continue
        column = _subject_column(rows)
        if column is None:
            continue
        year = _year_above(table)
        for row in rows:
            if column >= len(row):
                continue
            name = clean_subject(row[column])
            if not name or not _looks_like_a_name(name) or comparison_key(name) in seen:
                continue
            seen.add(comparison_key(name))
            subjects.append(blank_record(
                "materias", universidad_nombre=UNIVERSITY, carrera_o_programa=career,
                nombre_materia=name, anio_cursada=year, turno=None,
                area_tematica=None, descripcion_breve=None, regimen=None,
                carga_horaria_semanal=None,
            ))
    if len(subjects) < MIN_SUBJECTS:
        return {"materias": [], "motivo": "la página no publica el plan como tabla"}
    long_names = sum(1 for row in subjects
                     if len(str(row["nombre_materia"])) > MAX_NAME_LENGTH)
    if long_names > len(subjects) / 5:
        return {"materias": [], "motivo": "la tabla no separa una materia por fila"}
    return {"materias": subjects, "motivo": None}
