"""Deterministic parsers for the public catalogue of the UTN.

The UTN is the first of the nine sites that publishes its offer as data
instead of as pages: the "Estudiar en UTN" search reads a public JSON
endpoint, ``/modules/mod_oferta_acad/web-oferta.php``, which returns the
catalogue of careers, the regional faculties that teach each one and the
documents of each plan. Nothing here is rendered by a browser and nothing is
guessed: the fields below are the ones that endpoint publishes.

It is also the first one whose faculties carry an address and a dean, so the
campuses, the offers and the authorities can be filled from the source.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any

from bs4 import BeautifulSoup

from rumbo_scraper.contracts import SECTION_FIELDS, blank_record
from rumbo_scraper.normalizers.text import clean_text, comparison_key

UNIVERSITY = "Universidad Tecnológica Nacional"
SHORT_NAME = "UTN"
BASE_URL = "https://www.utn.edu.ar"
DOMAIN = "utn.edu.ar"
SOURCE_URL = f"{BASE_URL}/es/estudiar-utn"
API_URL = f"{BASE_URL}/modules/mod_oferta_acad/web-oferta.php"
PLAN_BASE_URL = f"{BASE_URL}/images/oferta_academica/planes_estudio"

# The search offers four kinds of career and splits the postgraduate one into
# its subtypes. Each id is the value the endpoint itself expects.
CAREER_KINDS: tuple[tuple[str, str], ...] = (
    ("id_tipos_carreras=1", "Grado"),
    ("id_tipos_carreras=2", "Grado"),
    ("id_tipos_carreras=3", "Pregrado"),
    ("id_tipos_carreras=4", "Posgrado"),
)

# ``descripcion_subtipos_carreras`` as the endpoint writes it, mapped to the
# four kinds the contract accepts. A postgraduate course is not a degree and
# has no kind: it stays null and is reported instead of being invented.
POSTGRADUATE_KINDS = {
    "doctorado en ingenieria": "Doctorado",
    "doctorado en informatica": "Doctorado",
    "doctorado": "Doctorado",
    "maestria": "Maestría",
    "especializacion": "Especialización",
    "curso": None,
}

# The search page keeps the selected career in the query string, so every row
# has a public address of its own.
def career_url(record: dict[str, Any]) -> str:
    kind = record.get("id_tipos_carreras")
    query = f"tipo_busqueda=carreras&id_tipos_carreras={kind}"
    if kind == "4":
        query += f"&posgrado={_POSTGRADUATE_SLUGS.get(str(record.get('id_subtipos_carreras')), '')}"
    return f"{SOURCE_URL}?{query}&idSeleccion={record.get('id_carreras')}"


_POSTGRADUATE_SLUGS = {"3": "doctorado", "7": "doctorado", "4": "maestria",
                       "5": "especializacion", "6": "curso"}


def programme_name(subtype: object, name: str) -> str:
    """Name a postgraduate the way the search displays it.

    The catalogue keeps the kind and the topic in two fields: a doctorate is
    filed as "Doctorado en Ingeniería" with the name "Electrónica", and the
    same topic is offered both as a "Maestría" and as an "Especialización".
    Storing only the topic would make those two collide into one programme, so
    the published kind is put back in front of the published topic and nothing
    else is added.
    """
    kind = clean_text(subtype)
    if not kind or comparison_key(kind) == comparison_key(name):
        return name
    separator = " — " if " en " in f" {comparison_key(kind)} " else " en "
    return f"{kind}{separator}{name}"


def catalogue_url(query: str) -> str:
    return f"{API_URL}?tipo_busqueda=carreras&{query}"


def offers_url(career_id: str) -> str:
    return f"{API_URL}?tipo_busqueda=carreras&id_carreras={career_id}"


def documents_url(career_id: str) -> str:
    return f"{API_URL}?tipo_busqueda=carreras&doc_id_carreras={career_id}"


def zone_url(zone: int) -> str:
    return f"{API_URL}?tipo_busqueda=sedes&id_zonas={zone}"


# The search only ever asks for these zones; there is no endpoint that lists
# them, so the spider walks the range and keeps the ones that answer.
ZONES = tuple(range(1, 8))


@dataclass(frozen=True)
class Career:
    """One row of the catalogue, with the level the search filed it under."""

    id: str
    name: str
    level: str
    kind: str | None
    url: str
    duration: str | None
    scope: str | None
    requirements: str | None


def _strip_html(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        return ""
    return clean_text(BeautifulSoup(value, "html.parser").get_text(" ", strip=True))


def read_catalogue(pages: dict[str, list[dict[str, Any]]]) -> tuple[Career, ...]:
    """Turn the four catalogue answers into careers, keeping the first level.

    A career appears once per filter it matches, so the same id can come back
    from two calls; the level of the first answer wins because the endpoint
    returns them in the order the menu offers them.
    """
    careers: dict[str, Career] = {}
    for query, level in CAREER_KINDS:
        for record in pages.get(catalogue_url(query), []):
            career_id = str(record.get("id_carreras") or "")
            name = clean_text(record.get("nombre_carreras"))
            if not career_id or not name or career_id in careers:
                continue
            kind = None
            if level == "Posgrado":
                subtype = record.get("descripcion_subtipos_carreras")
                kind = POSTGRADUATE_KINDS.get(comparison_key(subtype))
                # A course keeps the name the catalogue publishes; the degrees
                # carry their kind so two of them cannot share one row.
                if kind:
                    name = programme_name(subtype, name)
            careers[career_id] = Career(
                career_id, name, level, kind, career_url(record),
                # These belong to the career, not to the regional faculties
                # that teach it, so they come from the catalogue.
                record.get("duracion"), record.get("alcance"),
                record.get("requisitos"),
            )
    return tuple(careers.values())


def plan_document_url(documents: list[dict[str, Any]]) -> str | None:
    """Find the document the catalogue files as the study plan."""
    for record in documents:
        label = comparison_key(record.get("descripcion_tipos_doc_carreras"))
        archive = clean_text(record.get("archivo"))
        extension = clean_text(record.get("tipo_archivo"))
        if label == "plan de estudio" and archive and extension:
            return f"{PLAN_BASE_URL}/{archive}.{extension}"
    return None


# ---------------------------------------------------------------------------
# Durations
# ---------------------------------------------------------------------------

_HALF = {"½": 0.5, "⅓": 1 / 3, "¼": 0.25}


def duration_years(value: object) -> float | None:
    """Read the number of years out of the duration the catalogue publishes.

    The field is free HTML and the sources write the half year in three ways:
    ``5½``, ``5 años y medio`` and ``5 (CINCO) años``.
    """
    text = _strip_html(value)
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*([½⅓¼])?", text) if text else None
    if not match:
        return None
    years = float(match.group(1).replace(",", "."))
    if match.group(2):
        years += _HALF[match.group(2)]
    elif re.search(r"y\s+medio", text, re.I):
        years += 0.5
    return years if 0 < years <= 10 else None


def duration_hours(value: object) -> int | None:
    """Read the total clock hours the duration field states."""
    text = _strip_html(value)
    match = re.search(r"(\d{3,5})\s*horas", text, re.I)
    if not match:
        match = re.search(r"Horas reloj\s*:?\s*(\d{3,5})", text, re.I)
    return int(match.group(1)) if match else None


# ---------------------------------------------------------------------------
# Addresses
# ---------------------------------------------------------------------------

CABA = "Ciudad Autónoma de Buenos Aires"


def parse_address(value: object) -> dict[str, str | None]:
    """Split the address of a regional faculty into the contract's fields.

    The catalogue writes it as ``París 532. (1706) Haedo. Buenos Aires``. The
    postal code in brackets is the anchor: what comes before it is the street
    and what comes after it is the locality and the province. Two faculties
    publish no postal code, so the dot-separated tail is the fallback and a
    locality that cannot be read stays null.
    """
    text = clean_text(value)
    if not text:
        return {"calle": None, "numero": None, "localidad": None,
                "provincia": None, "codigo_postal": None}
    postal = re.search(r"\(([A-Za-z0-9 ]{4,10})\)", text)
    if postal:
        head, tail = text[:postal.start()], text[postal.end():]
        code = clean_text(postal.group(1))
    else:
        # Without the postal code the only safe anchor is a street number:
        # "Laprida 651. Venado Tuerto. Santa Fe" can be split, an address
        # written as "Maestro M. López y Cruz Roja Argentina. Córdoba" cannot,
        # and half of it would be a locality that was never published.
        parts = [clean_text(part) for part in text.split(".") if clean_text(part)]
        code = None
        if len(parts) >= 3 and re.search(r"\d+\s*$", parts[0]):
            head, tail = parts[0], ". ".join(parts[1:])
        else:
            head, tail = text, ""
    pieces = [clean_text(part) for part in tail.split(".") if clean_text(part)]
    locality = pieces[0] if pieces else None
    province = pieces[1] if len(pieces) > 1 else None
    if locality and comparison_key(locality) == comparison_key(CABA):
        locality, province = CABA, "CABA"
    street = clean_text(head).rstrip(" .,-")
    number = None
    number_match = re.search(r"(\d+)\s*$", street)
    if number_match:
        number = number_match.group(1)
        street = clean_text(street[:number_match.start()]).rstrip(" .,-")
    return {"calle": street or None, "numero": number, "localidad": locality,
            "provincia": province, "codigo_postal": code}


# The plan documents are read by the shared reader: the UTN and the UBA write
# their plans in the same four shapes, so the state machine that reads them
# does not belong to either.

from rumbo_scraper.parsers.plan_documents import (  # noqa: E402
    parse_plan_pdf as _read_plan_pdf, parse_plan_text as _read_plan_text,
    year_column_position,
)


def parse_plan_pdf(pdf_bytes: bytes, programme: str) -> dict[str, Any]:
    """Read the subjects out of a plan document of this university."""
    return _read_plan_pdf(pdf_bytes, programme, UNIVERSITY)


def parse_plan_text(text: str, programme: str) -> dict[str, Any]:
    """Read the subjects of a plan out of its extracted text."""
    return _read_plan_text(text, programme, UNIVERSITY)


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

def _dean_role(sex: object) -> str:
    """The catalogue publishes the dean's gender, so the title follows it."""
    return "Decana" if comparison_key(sex) == "f" else "Decano"


def _emails(value: object) -> list[str]:
    return [clean_text(part) for part in re.split(r"[,;]", clean_text(value))
            if "@" in part]


def build_dataset(
    careers: tuple[Career, ...],
    regionals: dict[str, dict[str, Any]],
    offers: dict[str, list[dict[str, Any]]],
    documents: dict[str, list[dict[str, Any]]],
    plans: dict[str, bytes] | None = None,
    errors: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Assemble the UTN dataset from the catalogue endpoint and the plans."""
    data: dict[str, list[dict[str, Any]]] = {section: [] for section in SECTION_FIELDS}
    data["universidades"] = [blank_record(
        "universidades", nombre_oficial=UNIVERSITY, nombre_corto=SHORT_NAME,
        # The UTN is the first public university of the eight loaded so far;
        # "Estatal" is the word the shared schema's enum uses for that.
        tipo_gestion="Estatal", sitio_web=BASE_URL,
    )]

    plans = plans or {}
    localities: dict[str, dict[str, Any]] = {}
    for regional in sorted(regionals.values(), key=lambda row: clean_text(row.get("nombre_regionales"))):
        name = clean_text(regional.get("nombre_regionales"))
        address = parse_address(regional.get("direccion"))
        if address["localidad"]:
            key = f"{address['localidad']}|{address['provincia']}"
            localities.setdefault(key, blank_record(
                "localidades", nombre_localidad=address["localidad"],
                provincia=address["provincia"], codigo_postal=address["codigo_postal"],
            ))
        data["sedes"].append(blank_record(
            "sedes", universidad_nombre=UNIVERSITY, nombre_sede=name,
            localidad=address["localidad"], calle=address["calle"],
            numero=address["numero"], tipo_sede="Campus",
        ))
        data["facultades"].append(blank_record(
            "facultades", universidad_nombre=UNIVERSITY, nombre_facultad=name,
            # The source calls it a "Facultad Regional"; the shared schema's
            # enum of unit kinds only has "Facultad", and the name keeps the rest.
            tipo_unidad="Facultad", sede=name,
        ))
        dean = clean_text(regional.get("decano"))
        if dean:
            data["autoridades"].append(blank_record(
                "autoridades", facultad_nombre=name, carrera=None,
                cargo=_dean_role(regional.get("sexo_decano")), tipo="Académico",
                nombre_autoridad=dean,
            ))
        for email in _emails(regional.get("email")):
            data["redes_contacto"].append(blank_record(
                "redes_contacto", universidad_nombre=UNIVERSITY, facultad_nombre=name,
                canal="Email", usuario_o_direccion=email,
            ))
        phone = clean_text(regional.get("telefono"))
        if phone:
            data["redes_contacto"].append(blank_record(
                "redes_contacto", universidad_nombre=UNIVERSITY, facultad_nombre=name,
                canal="Teléfono", usuario_o_direccion=phone,
            ))
    data["localidades"] = list(localities.values())

    details: list[dict[str, Any]] = []
    resources: list[dict[str, Any]] = []
    unreadable_plans: list[dict[str, str]] = []
    without_kind: list[str] = []
    discarded_rows = 0
    plans_without_year: list[str] = []
    for career in careers:
        career_offers = offers.get(offers_url(career.id), [])
        campuses = [clean_text(row.get("nombre_regionales")) for row in career_offers]
        plan_url = plan_document_url(documents.get(documents_url(career.id), []))
        subjects: list[dict[str, Any]] = []
        if plan_url and plans.get(plan_url):
            plan = parse_plan_pdf(plans[plan_url], career.name)
            subjects = plan["materias"]
            discarded_rows += plan["descartadas"]
            if subjects and not any(row["anio_cursada"] for row in subjects):
                plans_without_year.append(career.name)
            if plan["motivo"]:
                unreadable_plans.append({"carrera": career.name, "url": plan_url,
                                         "motivo": plan["motivo"]})
        elif plan_url:
            unreadable_plans.append({"carrera": career.name, "url": plan_url,
                                     "motivo": "el documento no se pudo descargar"})
        data["materias"].extend(subjects)
        if plan_url:
            resources.append({
                "entidad_tipo": "posgrado" if career.level == "Posgrado" else "carrera",
                "entidad_nombre": career.name, "tipo_recurso": "documento",
                "titulo": f"Plan de estudios de {career.name}",
                "url": plan_url, "fuente_url": career.url,
            })
        details.append({
            "id": career.id, "nombre": career.name, "nivel": career.level,
            "tipo_posgrado": career.kind, "url": career.url, "plan_url": plan_url,
            "sedes": campuses, "materias": len(subjects),
        })

        if career.level == "Posgrado":
            if not career.kind:
                without_kind.append(career.name)
            data["posgrados"].append(blank_record(
                "posgrados", universidad_nombre=UNIVERSITY,
                facultad_nombre=campuses[0] if len(campuses) == 1 else None,
                nombre_programa=career.name, tipo_posgrado=career.kind,
                titulo_otorgado=None, sede=campuses[0] if len(campuses) == 1 else None,
                modalidad=None, duracion_meses=None,
                requiere_tesis_trabajo_final=None, requisito_titulo_previo=None,
                cohorte_inicio=None, costo_total_programa=None, moneda=None,
                descripcion_breve=None, url_oficial=career.url,
            ))
            continue

        data["carreras"].append(blank_record(
            "carreras", universidad_nombre=UNIVERSITY, facultad_nombre=None,
            nombre_carrera=career.name, denominacion_canonica=career.name,
            nivel=career.level, titulo_otorgado=None, tiene_titulo_intermedio=None,
            duracion_anios=duration_years(career.duration),
            # The scope is the only prose the catalogue publishes about a
            # career: the professional activities its graduate may perform.
            descripcion_breve=_strip_html(career.scope) or None,
            cantidad_materias_total=len(subjects) or None,
        ))
        for offer in career_offers:
            campus = clean_text(offer.get("nombre_regionales"))
            if not campus:
                continue
            data["ofertas"].append(blank_record(
                "ofertas", universidad_nombre=UNIVERSITY, facultad_nombre=campus,
                carrera_nombre=career.name, sede=campus, modalidad=None,
                regimen_ingreso=_strip_html(career.requirements) or None,
                coneau_resolucion=clean_text(offer.get("res_coneau")) or None,
                coneau_vigencia_hasta=None, tiene_pasantias=None,
                tiene_bolsa_trabajo=None, url_oficial=career.url,
            ))

    missing = [section for section, rows in data.items() if not rows]
    return {
        "universidad": UNIVERSITY,
        "fuente_principal": SOURCE_URL,
        "extraido_en": datetime.now(timezone.utc).isoformat(),
        "metodo": "JSON público del buscador de oferta académica y planes en PDF; sin IA",
        "datos": data,
        "recursos_publicos": resources,
        "detalle_carreras": details,
        "directorio_academico": {"personas": [], "roles_academicos": []},
        "control_calidad": {
            "secciones_vacias": missing,
            "secciones_sin_fuente_publica": {
                # The endpoint publishes the catalogue and nothing else; the
                # rest lives on each regional faculty's own site.
                "aranceles": "la universidad es pública y no publica aranceles",
                # Checked against the catalogue and against the ninety-one
                # plan documents: neither states the degree a career awards.
                "carreras.titulo_otorgado": "ni el catálogo ni los planes "
                                            "publican el título que expide",
                # The endpoint returns these empty for all 557 postgraduate
                # programmes: it publishes their name and their kind only.
                "posgrados.titulo_otorgado": "el buscador sólo publica el "
                                             "nombre y el tipo del posgrado",
                "posgrados.duracion_meses": "el buscador no publica la "
                                            "duración de los posgrados",
                "posgrados.modalidad": "el buscador no publica la modalidad "
                                       "de los posgrados",
                "posgrados.requisito_titulo_previo": "el buscador no publica "
                                                     "los requisitos de ingreso",
                "posgrados.descripcion_breve": "el buscador no publica una "
                                               "descripción de los posgrados",
                "becas": "el buscador central no publica becas",
                "turnos_anio": "el buscador no publica horarios",
                "ofertas_ciclo": "el buscador no publica ciclos de inscripción",
                "areas_tematicas": "el catálogo no agrupa las materias por área",
                "actividades": "el catálogo no publica prácticas ni pasantías",
                "servicios_estudiantiles": "no hay catálogo central de servicios",
                "actividades_extracurriculares": "no hay catálogo central",
                "alojamiento": "no hay catálogo central",
                "programas_internacionales": "no hay catálogo central",
                "convenios_intercambio": "no hay catálogo central",
            },
            "carreras_descubiertas": len(careers),
            "planes_no_legibles": unreadable_plans,
            "planes_sin_anio_publicado": plans_without_year,
            "filas_descartadas_de_los_planes": discarded_rows,
            "posgrados_sin_tipo_en_contrato": without_kind,
            "errores_descarga": errors or [],
            "nota": "Los valores ausentes permanecen nulos; no se inventan datos.",
        },
    }
