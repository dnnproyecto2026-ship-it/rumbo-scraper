"""Parsers and dataset builder for Universidad Torcuato Di Tella."""

from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from rumbo_scraper.contracts import SECTION_FIELDS, blank_record
from rumbo_scraper.normalizers.text import clean_text, comparison_key


UNIVERSITY = "Universidad Torcuato Di Tella"
BASE_URL = "https://www.utdt.edu"
SOURCE_URL = f"{BASE_URL}/listado_contenidos.php?id_item_menu=359"
INSTITUTION_URL = f"{BASE_URL}/ver_contenido.php?id_contenido=1006&id_item_menu=140"
AUTHORITIES_URL = f"{BASE_URL}/autoridades/listado_contenidos.php?id_item_menu=26532"
STUDENT_SERVICES_URL = f"{BASE_URL}/ver_contenido.php?id_contenido=10891&id_item_menu=21282"
LOCALITY = "Ciudad Autónoma de Buenos Aires — CABA"
CAMPUS = f"{UNIVERSITY} — Campus Di Tella — {LOCALITY}"


@dataclass(frozen=True)
class CareerConfig:
    short_name: str
    canonical_name: str
    faculty: str
    faculty_type: str
    detail_url: str


CAREERS: dict[str, CareerConfig] = {
    "abogacia": CareerConfig("Abogacía", "Abogacía", "Derecho", "Escuela", f"{BASE_URL}/ver_contenido.php?id_contenido=9447&id_item_menu=18407"),
    "arquitectura": CareerConfig("Arquitectura", "Arquitectura", "Arquitectura y Estudios Urbanos", "Escuela", f"{BASE_URL}/ver_contenido.php?id_contenido=23863&id_item_menu=39620"),
    "diseno": CareerConfig("Diseño", "Licenciatura en Diseño", "Diseño", "Escuela", f"{BASE_URL}/ver_contenido.php?id_contenido=26457&id_item_menu=43582"),
    "administracion de empresas": CareerConfig("Administración de Empresas", "Licenciatura en Administración de Empresas", "Negocios", "Escuela", f"{BASE_URL}/ver_contenido.php?id_contenido=7907&id_item_menu=15483"),
    "economia empresarial": CareerConfig("Economía Empresarial", "Licenciatura en Economía Empresarial", "Negocios", "Escuela", f"{BASE_URL}/ver_contenido.php?id_contenido=570&id_item_menu=218"),
    "economia": CareerConfig("Economía", "Licenciatura en Economía", "Economía", "Departamento", f"{BASE_URL}/ver_contenido.php?id_contenido=123&id_item_menu=643"),
    "ingenieria industrial": CareerConfig("Ingeniería Industrial", "Ingeniería Industrial", "Ingeniería y Ciencia Aplicada", "Escuela", f"{BASE_URL}/ver_contenido.php?id_contenido=26059&id_item_menu=41405"),
    "tecnologia digital": CareerConfig("Tecnología Digital", "Licenciatura en Tecnología Digital", "Negocios", "Escuela", f"{BASE_URL}/ver_contenido.php?id_contenido=19866&id_item_menu=31534"),
    "ciencias del comportamiento": CareerConfig("Ciencias del Comportamiento", "Licenciatura en Ciencias del Comportamiento", "Negocios", "Escuela", f"{BASE_URL}/ver_contenido.php?id_contenido=24484&id_item_menu=40415"),
    "estudios internacionales": CareerConfig("Estudios Internacionales", "Licenciatura en Estudios Internacionales", "Ciencia Política y Estudios Internacionales", "Departamento", f"{BASE_URL}/ver_contenido.php?id_contenido=144&id_item_menu=757"),
    "ciencia politica y gobierno": CareerConfig("Ciencia Política y Gobierno", "Licenciatura en Ciencia Política y Gobierno", "Ciencia Política y Estudios Internacionales", "Departamento", f"{BASE_URL}/ver_contenido.php?id_contenido=119&id_item_menu=727"),
    "ciencias sociales": CareerConfig("Ciencias Sociales", "Licenciatura en Ciencias Sociales", "Estudios Históricos y Sociales", "Departamento", f"{BASE_URL}/ver_contenido.php?id_contenido=9776&id_item_menu=19232"),
    "historia": CareerConfig("Historia", "Licenciatura en Historia", "Estudios Históricos y Sociales", "Departamento", f"{BASE_URL}/ver_contenido.php?id_contenido=465&id_item_menu=112"),
}

CAREER_ALIASES = {key: value.canonical_name for key, value in CAREERS.items()}

ACADEMIC_UNITS = (
    ("Arquitectura y Estudios Urbanos", "Escuela"), ("Derecho", "Escuela"),
    ("Diseño", "Escuela"), ("Gobierno", "Escuela"),
    ("Ingeniería y Ciencia Aplicada", "Escuela"), ("Negocios", "Escuela"),
    ("Ciencia Política y Estudios Internacionales", "Departamento"),
    ("Economía", "Departamento"), ("Estudios Históricos y Sociales", "Departamento"),
    ("Matemática y Estadística", "Departamento"), ("Arte", "Centro"),
)

AUTHORITY_SECTIONS = {
    "Escuela de Arquitectura y Estudios Urbanos": "Arquitectura y Estudios Urbanos",
    "Escuela de Derecho": "Derecho",
    "Escuela de Diseño": "Diseño",
    "Escuela de Gobierno": "Gobierno",
    "Escuela de Ingeniería y Ciencia Aplicada": "Ingeniería y Ciencia Aplicada",
    "Escuela de Negocios": "Negocios",
    "Centro de Arte": "Arte",
    "Departamento de Ciencia Política y Estudios Internacionales": "Ciencia Política y Estudios Internacionales",
    "Departamento de Economía": "Economía",
    "Departamento de Estudios Históricos y Sociales": "Estudios Históricos y Sociales",
    "Departamento de Matemática y Estadística": "Matemática y Estadística",
}

PROFESSOR_PAGES = {
    "Arquitectura y Estudios Urbanos": f"{BASE_URL}/ver_contenido.php?id_contenido=24043&id_item_menu=39866",
    "Derecho": f"{BASE_URL}/listado_contenidos.php?id_item_menu=3789",
    "Diseño": f"{BASE_URL}/ver_contenido.php?id_contenido=25833&id_item_menu=42551",
    "Gobierno": f"{BASE_URL}/ver_contenido.php?id_contenido=1817&id_item_menu=3792",
    "Ingeniería y Ciencia Aplicada": f"{BASE_URL}/ver_contenido.php?id_contenido=26257&id_item_menu=43279",
    "Negocios": f"{BASE_URL}/ver_contenido.php?id_contenido=1808&id_item_menu=3786",
    "Ciencia Política y Estudios Internacionales": f"{BASE_URL}/ver_contenido.php?id_contenido=16314&id_item_menu=27135",
    "Economía": f"{BASE_URL}/ver_contenido.php?id_contenido=1685&id_item_menu=3549",
    "Estudios Históricos y Sociales": f"{BASE_URL}/listado_contenidos.php?id_item_menu=3798",
    "Matemática y Estadística": f"{BASE_URL}/listado_contenidos.php?id_item_menu=508",
}

NAME_REJECT_TERMS = (
    "profesor", "cuerpo", "departamento", "escuela", "universidad", "miembro",
    "comite", "staff", "full-time", "part-time", "dedicacion", "institucional",
    "autoridad", "campus", "ingresante", "unidad", "programa", "director",
    "decano", "coordin", "investigador", "ordinario", "visitante", "emerito",
    "honorario", "contacto", "secretaria", "consejo", "evaluacion",
    "university", "universidad", "school", "foundation", "college", "faculty",
    "uba", "utdt", "mit", "uca", "unlp", "insead", "ucla", "etsam", "univ",
    "mba", "master", "magister", "doctor", "phd", "licenciado", "abogado",
    "contador", "ciencias", "sciences", "arquitectura", "urbanismo", "design",
    "historia", "teoria", "proyecto arquitectonico", "finanzas",
)

AREA_KEYWORDS = {
    "Matemática y Estadística": ("matemat", "calculo", "algebra", "estadistic", "econometr"),
    "Programación y Tecnología": ("program", "comput", "datos", "digital", "software", "tecnolog", "inteligencia artificial", "algorit"),
    "Ciencias Naturales": ("fisica", "quimica", "biolog"),
    "Ciencias Sociales": ("derecho", "politic", "sociolog", "sociedad", "relaciones internacionales"),
    "Humanidades": ("historia", "filosof", "etica", "literatura", "cultura"),
    "Negocios y Economía": ("econom", "finanzas", "administr", "marketing", "contabilidad", "negocios"),
    "Comunicación e Idiomas": ("comunic", "escritura", "idioma", "ingles", "oratoria"),
    "Salud": ("salud", "neuro"),
    "Arte y Diseño": ("arte", "diseno", "arquitect", "proyecto", "morfolog", "urban"),
    "Practica Profesional / Pasantías": ("practica profesional", "pasant"),
}


@dataclass(frozen=True)
class UTDTCareer:
    nombre_carrera: str
    denominacion_canonica: str
    nivel: str
    universidad_nombre: str
    fuente_url: str
    scraped_at: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _soup(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style", "noscript"]):
        element.decompose()
    return soup


def _present_configs(page_text: str) -> list[CareerConfig]:
    key = comparison_key(page_text)
    matches: list[tuple[int, CareerConfig]] = []
    for alias, config in CAREERS.items():
        match = re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", key)
        if match:
            matches.append((match.start(), config))
    return [config for _, config in sorted(matches, key=lambda item: item[0])]


def parse_careers(html: str, source_url: str = SOURCE_URL) -> list[UTDTCareer]:
    soup = _soup(html)
    configs = _present_configs(clean_text(soup.get_text(" ", strip=True)))
    scraped_at = datetime.now(timezone.utc).isoformat()
    return [UTDTCareer(
        nombre_carrera=config.short_name,
        denominacion_canonica=config.canonical_name,
        nivel="Grado", universidad_nombre=UNIVERSITY,
        fuente_url=source_url, scraped_at=scraped_at,
    ) for config in configs]


def _labeled_value(soup: BeautifulSoup, label: str) -> str | None:
    wanted = comparison_key(label)
    for node in soup.find_all(["h2", "h3", "h4", "h5", "h6", "strong", "b"]):
        if comparison_key(node.get_text(" ", strip=True)).rstrip(":") != wanted:
            continue
        for candidate in node.find_all_next(["h2", "h3", "h4", "h5", "h6", "p"], limit=6):
            value = clean_text(candidate.get_text(" ", strip=True))
            if value and comparison_key(value).rstrip(":") != wanted and len(value) <= 120:
                return value
    return None


def _years(value: str | None) -> float | None:
    match = re.search(r"(\d+(?:[,.]\d+)?)\s*anos?", comparison_key(value or ""))
    return float(match.group(1).replace(",", ".")) if match else None


def _modality(value: str | None) -> str | None:
    key = comparison_key(value or "")
    if "hibrid" in key:
        return "Híbrida"
    if "virtual" in key and "presencial" not in key:
        return "Virtual"
    if "presencial" in key:
        return "Presencial"
    return None


def _description(soup: BeautifulSoup) -> str | None:
    meta = soup.find("meta", attrs={"name": re.compile("description", re.I)})
    if meta and meta.get("content"):
        value = clean_text(str(meta["content"]))
        if len(value) >= 50:
            return value[:1000]
    for paragraph in soup.find_all("p"):
        value = clean_text(paragraph.get_text(" ", strip=True))
        if 120 <= len(value) <= 1000 and "cookies" not in comparison_key(value):
            return value
    return None


def _director(soup: BeautifulSoup) -> str | None:
    marker = soup.find(string=re.compile(r"Director(?:a)? de la carrera", re.I))
    if not marker:
        return None
    for node in marker.parent.find_all_previous(["a", "h2", "h3", "h4", "h5", "h6"], limit=12):
        value = clean_text(node.get_text(" ", strip=True))
        if 2 <= len(value.split()) <= 6 and not any(term in comparison_key(value) for term in ("director", "carrera", "universidad", "escuela", "departamento")):
            return value
    return None


def parse_career_detail(html: str, config: CareerConfig) -> dict[str, object]:
    soup = _soup(html)
    text = comparison_key(clean_text(soup.get_text(" ", strip=True)))
    plan_url = None
    for anchor in soup.find_all("a", href=True):
        if "plan de estudios" in comparison_key(anchor.get_text(" ", strip=True)):
            plan_url = urljoin(config.detail_url, anchor["href"])
            break
    return {
        "duracion_anios": _years(_labeled_value(soup, "Duración")),
        "modalidad": _modality(_labeled_value(soup, "Modalidad")),
        "lugar": _labeled_value(soup, "Lugar"),
        "descripcion_breve": _description(soup), "director": _director(soup),
        "tiene_pasantias": "Si" if "pasant" in text else "No",
        "tiene_bolsa_trabajo": "Si" if any(term in text for term in ("di tella gateway", "ditella gateway", "desarrollo profesional", "bolsa de trabajo")) else "No",
        "plan_url": plan_url,
    }


def classify_area(subject: str) -> str:
    key = comparison_key(subject)
    for area, keywords in AREA_KEYWORDS.items():
        if any(keyword in key for keyword in keywords):
            return area
    return "Otro"


def parse_study_plan(html: str, career_name: str) -> dict[str, object]:
    soup = _soup(html)
    lines = [clean_text(x) for x in soup.get_text("\n", strip=True).splitlines() if clean_text(x)]
    title = None
    duration = None
    for line in lines:
        title_match = re.match(r"t[ií]tulo\s*:\s*(.+)", line, re.I)
        if title_match and not title:
            title = clean_text(title_match.group(1))
        if comparison_key(line).startswith("duracion:") and duration is None:
            duration = _years(line)
    subjects: list[dict[str, object]] = []
    current_year: int | None = None
    semester: int | None = None
    for node in soup.find_all(["h2", "h3", "h4", "h5", "h6", "li"]):
        value = clean_text(node.get_text(" ", strip=True))
        key = comparison_key(value)
        year_match = re.fullmatch(r"([1-6])", key)
        if node.name != "li" and year_match:
            current_year = int(year_match.group(1)); semester = None; continue
        semester_match = re.search(r"([12]).*semestre", key)
        if node.name != "li" and semester_match:
            semester = int(semester_match.group(1)); continue
        if node.name != "li" or current_year is None or not (2 <= len(value) <= 120):
            continue
        if any(term in key for term in ("contacto", "whatsapp", "universidad", "ver mas", "inscripcion")):
            continue
        subjects.append(blank_record(
            "materias", universidad_nombre=UNIVERSITY,
            carrera_o_programa=career_name, nombre_materia=value,
            anio_cursada=current_year, turno=None,
            area_tematica=classify_area(value), descripcion_breve=None,
            regimen="Cuatrimestral" if semester else None,
            carga_horaria_semanal=None,
        ))
    return {"titulo_otorgado": title, "duracion_anios": duration, "materias": subjects}


def _faculty_link(config: CareerConfig) -> str:
    return f"{UNIVERSITY} — {config.faculty_type} de {config.faculty}"


def parse_faculty_authorities(html: str) -> list[dict[str, object]]:
    """Extract current school/department leadership from the official page."""
    soup = _soup(html)
    unit_types = {name: unit_type for name, unit_type in ACADEMIC_UNITS}
    records: list[dict[str, object]] = []
    seen: set[tuple[str, str, str]] = set()
    for heading in soup.find_all("h4"):
        section = clean_text(heading.get_text(" ", strip=True))
        faculty = AUTHORITY_SECTIONS.get(section)
        if not faculty:
            continue
        for node in heading.find_all_next(["h4", "strong"]):
            if node.name == "h4":
                break
            value = clean_text(node.get_text(" ", strip=True)).rstrip(".")
            if ":" not in value:
                continue
            role, name = (clean_text(part) for part in value.split(":", 1))
            role_key = comparison_key(role)
            if not (role_key.startswith("decano") or role_key.startswith("decana") or role_key.startswith("director") or role_key.startswith("directora")):
                continue
            name = name.rstrip(".")
            if not name or len(name.split()) < 2:
                continue
            identity = (faculty, role, name)
            if identity in seen:
                continue
            seen.add(identity)
            unit_type = unit_types[faculty]
            records.append(blank_record(
                "autoridades",
                facultad_nombre=f"{UNIVERSITY} — {unit_type} de {faculty}",
                carrera=None,
                cargo=role,
                tipo="Autoridad de unidad académica",
                nombre_autoridad=name,
            ))
    return records


def _person_name(value: str) -> str | None:
    value = clean_text(value).strip(" .|")
    key = comparison_key(value)
    if not value or ":" in value or any(char.isdigit() for char in value):
        return None
    if any(term in key for term in NAME_REJECT_TERMS):
        return None
    words = value.replace(",", " ").split()
    if not 2 <= len(words) <= 7 or len(value) > 90:
        return None
    word_pattern = re.compile(r"^[A-ZÁÉÍÓÚÜÑ][A-Za-zÁÉÍÓÚÜÑáéíóúüñ’'.-]*$")
    particles = {"de", "del", "la", "las", "los", "y", "di"}
    if not all(word_pattern.match(word) or word.lower() in particles for word in words):
        return None
    if "," in value:
        surname, given = (clean_text(part) for part in value.split(",", 1))
        value = f"{given} {surname}"
    return value.rstrip(".")


def parse_professor_page(html: str, faculty: str, source_url: str) -> list[dict[str, object]]:
    """Extract the people explicitly listed on an official faculty roster."""
    soup = _soup(html)
    root = soup.find(id="contenido") or soup.find("article") or soup
    grouped_links: dict[str, str] = {}
    for anchor in root.find_all("a", href=True):
        label = clean_text(anchor.get_text(" ", strip=True))
        if label:
            href = urljoin(source_url, anchor["href"])
            grouped_links[href] = clean_text(f"{grouped_links.get(href, '')} {label}")
    candidates: list[tuple[str, str | None]] = []
    for href, label in grouped_links.items():
        name = _person_name(label)
        if name:
            candidates.append((name, href))
    for node in root.find_all(["strong", "h3", "h4"]):
        if node.find("a"):
            continue
        name = _person_name(node.get_text(" ", strip=True))
        if name:
            candidates.append((name, None))
    for line in root.get_text("\n", strip=True).splitlines():
        match = re.match(r"^([A-ZÁÉÍÓÚÜÑ][^.\n]{2,90},\s*[A-ZÁÉÍÓÚÜÑ][^.\n]{1,60})\.", clean_text(line))
        if match:
            name = _person_name(match.group(1))
            if name:
                candidates.append((name, None))
    seen: set[str] = set()
    records: list[dict[str, object]] = []
    for name, profile_url in candidates:
        identity = comparison_key(name)
        if identity in seen:
            continue
        seen.add(identity)
        records.append({
            "universidad_nombre": UNIVERSITY,
            "nombre_completo": name,
            "email": None,
            "perfil_url": profile_url,
            "formacion": None,
            "biografia": None,
            "fuente_url": source_url,
            "facultad_nombre": faculty,
        })
    return records


def build_academic_directory(
    authorities: list[dict[str, object]],
    professor_pages: dict[str, str],
) -> dict[str, list[dict[str, object]]]:
    people: dict[str, dict[str, object]] = {}
    roles: list[dict[str, object]] = []
    role_keys: set[tuple[object, ...]] = set()

    def add_person(name: str, source_url: str, profile_url: str | None = None) -> None:
        identity = comparison_key(name)
        current = people.setdefault(identity, {
            "universidad_nombre": UNIVERSITY, "nombre_completo": name,
            "email": None, "perfil_url": profile_url, "formacion": None,
            "biografia": None, "fuente_url": source_url,
        })
        if profile_url and not current["perfil_url"]:
            current["perfil_url"] = profile_url

    def add_role(**role: object) -> None:
        key = tuple(role.get(field) for field in (
            "nombre_completo", "facultad_nombre", "carrera_nombre",
            "materia_nombre", "cargo",
        ))
        if key not in role_keys:
            role_keys.add(key); roles.append(role)

    for row in authorities:
        name = str(row["nombre_autoridad"])
        add_person(name, AUTHORITIES_URL)
        add_role(
            nombre_completo=name, facultad_nombre=row["facultad_nombre"],
            carrera_nombre=row["carrera"], materia_nombre=None,
            cargo=row["cargo"], tipo_rol=row["tipo"], es_autoridad=True,
            fuente_url=AUTHORITIES_URL,
        )
    unit_types = {name: unit_type for name, unit_type in ACADEMIC_UNITS}
    for faculty, html in professor_pages.items():
        source_url = PROFESSOR_PAGES[faculty]
        faculty_ref = f"{UNIVERSITY} — {unit_types[faculty]} de {faculty}"
        for person in parse_professor_page(html, faculty, source_url):
            name = str(person["nombre_completo"])
            add_person(name, source_url, person.get("perfil_url"))
            add_role(
                nombre_completo=name, facultad_nombre=faculty_ref,
                carrera_nombre=None, materia_nombre=None, cargo="Profesor/a",
                tipo_rol="Docente", es_autoridad=False, fuente_url=source_url,
            )
    return {"personas": list(people.values()), "roles_academicos": roles}


def _contact_records(html: str) -> list[dict[str, object]]:
    soup = _soup(html)
    contacts = [("Sitio Web", BASE_URL), ("Email", "admisiones@utdt.edu"), ("WhatsApp", "+54 9 11 5699 6109")]
    domains = {"Instagram": "instagram.com", "TikTok": "tiktok.com", "LinkedIn": "linkedin.com", "Twitter": "twitter.com", "Facebook": "facebook.com", "YouTube": "youtube.com"}
    for channel, domain in domains.items():
        anchor = soup.find("a", href=lambda href: href and domain in href)
        if anchor:
            contacts.append((channel, anchor["href"]))
    return [blank_record("redes_contacto", universidad_nombre=UNIVERSITY, facultad_nombre=None, canal=channel, usuario_o_direccion=value) for channel, value in contacts]


def _postgraduates(html: str) -> list[dict[str, object]]:
    soup = _soup(html)
    records: list[dict[str, object]] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        name = clean_text(anchor.get_text(" ", strip=True)); key = comparison_key(name)
        if not name or name in seen or not any(word in key for word in ("maestria", "doctorado", "especializacion")):
            continue
        seen.add(name)
        kind = next((label for label in ("Maestría", "Doctorado", "Especialización") if comparison_key(label) in key), None)
        records.append(blank_record(
            "posgrados", universidad_nombre=UNIVERSITY, facultad_nombre=None,
            nombre_programa=name, tipo_posgrado=kind, titulo_otorgado=None,
            sede=CAMPUS, modalidad=None, duracion_meses=None,
            requiere_tesis_trabajo_final=None, requisito_titulo_previo=None,
            cohorte_inicio=None, costo_total_programa=None, moneda=None,
            descripcion_breve=None,
        ))
    return records


def build_dataset(admissions_html: str, institution_html: str, detail_pages: dict[str, str], plan_pages: dict[str, str], errors: list[dict[str, str]] | None = None, authorities_html: str = "", professor_pages: dict[str, str] | None = None) -> dict[str, object]:
    """Build all Excel sections from official pages without inventing values."""
    found = {item.denominacion_canonica for item in parse_careers(admissions_html)}
    sections: dict[str, list[dict[str, object]]] = {name: [] for name in SECTION_FIELDS}
    sections["localidades"] = [blank_record("localidades", nombre_localidad="Ciudad Autónoma de Buenos Aires", provincia="CABA", codigo_postal="C1428BCW")]
    contacts = _contact_records(admissions_html)
    lookup = {row["canal"]: row["usuario_o_direccion"] for row in contacts}
    sections["universidades"] = [blank_record(
        "universidades", nombre_oficial=UNIVERSITY, nombre_corto="UTDT",
        tipo_gestion="Privada", anio_fundacion=1991, sitio_web=BASE_URL,
        telefono_area="54 11", telefono_numero="5169 7000",
        mail_contacto="admisiones@utdt.edu", instagram=lookup.get("Instagram"),
        tiktok=lookup.get("TikTok"), linkedin=lookup.get("LinkedIn"),
        twitter=lookup.get("Twitter"), facebook=lookup.get("Facebook"), youtube=lookup.get("YouTube"),
    )]
    sections["sedes"] = [blank_record("sedes", universidad_nombre=UNIVERSITY, nombre_sede="Campus Di Tella", localidad=LOCALITY, calle="Av. Figueroa Alcorta", numero="7350", tipo_sede="Campus")]
    institution_key = comparison_key(_soup(institution_html).get_text(" ", strip=True))
    for name, unit_type in ACADEMIC_UNITS:
        if comparison_key(name) in institution_key:
            sections["facultades"].append(blank_record("facultades", universidad_nombre=UNIVERSITY, nombre_facultad=name, tipo_unidad=unit_type, sede=CAMPUS))
    cycle_match = re.search(r"marzo\s+(20\d{2})", comparison_key(_soup(admissions_html).get_text(" ", strip=True)))
    cycle_year = int(cycle_match.group(1)) if cycle_match else None

    for config in CAREERS.values():
        if config.canonical_name not in found:
            continue
        detail = parse_career_detail(detail_pages.get(config.detail_url, ""), config)
        plan_url = detail.get("plan_url")
        plan = parse_study_plan(plan_pages.get(str(plan_url), ""), config.short_name) if plan_url else {"titulo_otorgado": None, "duracion_anios": None, "materias": []}
        subjects = list(plan["materias"]); duration = detail.get("duracion_anios") or plan.get("duracion_anios"); faculty = _faculty_link(config)
        sections["carreras"].append(blank_record(
            "carreras", universidad_nombre=UNIVERSITY, facultad_nombre=faculty,
            nombre_carrera=config.short_name, denominacion_canonica=config.canonical_name,
            nivel="Grado", titulo_otorgado=plan.get("titulo_otorgado"),
            tiene_titulo_intermedio=None, duracion_anios=duration, es_art_43=None,
            descripcion_breve=detail.get("descripcion_breve"), cantidad_materias_total=len(subjects) or None,
        ))
        sections["ofertas"].append(blank_record(
            "ofertas", universidad_nombre=UNIVERSITY, facultad_nombre=faculty,
            carrera_nombre=config.short_name, sede=CAMPUS, modalidad=detail.get("modalidad"),
            regimen_ingreso=None, coneau_resolucion=None, coneau_vigencia_hasta=None,
            tiene_pasantias=detail.get("tiene_pasantias"), tiene_bolsa_trabajo=detail.get("tiene_bolsa_trabajo"),
        ))
        if cycle_year:
            sections["ofertas_ciclo"].append(blank_record(
                "ofertas_ciclo", universidad_nombre=UNIVERSITY, carrera_nombre=config.short_name,
                sede=CAMPUS, ciclo_anio=cycle_year, ciclo_nombre=f"Ingreso {cycle_year}",
                cupo_ingresantes=None, fecha_apertura_inscripcion=None,
                fecha_cierre_inscripcion=None, estado=None,
            ))
        sections["materias"].extend(subjects)
        for area, count in sorted(Counter(str(row["area_tematica"]) for row in subjects).items()):
            sections["areas_tematicas"].append(blank_record("areas_tematicas", universidad_nombre=UNIVERSITY, facultad_nombre=faculty, carrera_nombre=config.short_name, area_tematica=area, cantidad_materias=count))
        for subject in subjects:
            subject_key = comparison_key(str(subject["nombre_materia"]))
            activity_type = next((label for needle, label in (("practica", "Practica Profesional"), ("pasant", "Pasantía"), ("tesis", "Trabajo Final / Tesis"), ("seminario", "Seminario"), ("taller", "Taller"), ("intercambio", "Intercambio")) if needle in subject_key), None)
            if activity_type:
                sections["actividades"].append(blank_record("actividades", universidad_nombre=UNIVERSITY, carrera_o_programa=config.short_name, tipo_actividad=activity_type, nombre_actividad=subject["nombre_materia"], obligatoria=None, carga_horaria_total=None, descripcion_breve=None))
        if detail.get("director"):
            sections["autoridades"].append(blank_record("autoridades", facultad_nombre=faculty, carrera=config.short_name, cargo="Director/a de carrera", tipo="Académico", nombre_autoridad=detail["director"]))

    sections["posgrados"] = _postgraduates(institution_html)
    sections["autoridades"].extend(parse_faculty_authorities(authorities_html))
    sections["redes_contacto"] = contacts
    missing = {section: {field: sum(row[field] in (None, "") for row in records) for field in SECTION_FIELDS[section]} for section, records in sections.items()}
    return {
        "metadata": {"universidad": UNIVERSITY, "scraped_at": datetime.now(timezone.utc).isoformat(), "fuentes": [SOURCE_URL, INSTITUTION_URL, AUTHORITIES_URL, STUDENT_SERVICES_URL], "escritura_supabase": False},
        "datos": sections,
        "directorio_academico": build_academic_directory(
            sections["autoridades"], professor_pages or {}
        ),
        "control_calidad": {
            "secciones_vacias": [name for name, rows in sections.items() if not rows],
            "faltantes_por_campo": missing, "errores_descarga": errors or [],
            "advertencias": [
                "Los valores nulos indican información no publicada; no se inventan datos.",
                "Turnos y aranceles quedan vacíos hasta encontrar una fuente oficial verificable.",
                "Los posgrados descubiertos requieren otra pasada por sus páginas de detalle.",
            ],
        },
    }
