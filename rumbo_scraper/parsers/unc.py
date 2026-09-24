"""The careers the UNC lists in its official guides.

The UNC has no catalogue of its own careers on its main site: each faculty
publishes its careers on its own host (``fcefyn.unc.edu.ar``,
``famaf.unc.edu.ar``, ``sitio.ffyh.unc.edu.ar``...), and the general reader,
walking out from ``unc.edu.ar``, found a third of them and took subjects and
course names for careers ("Ingeniería de Microondas", "Profesorado y
Concursos"). The Academic Secretariat does publish two guides, one of grado
and one of pregrado, with every career, the faculty or school that teaches
it and a link to its page:

    <div class="carrera"><a href="https://derecho.unc.edu.ar/alumnos/abogacia/">
      <span>Abogacía </span> | Facultad de Derecho </a></div>

That is the list of the UNC's careers, in the university's own words.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from rumbo_scraper.normalizers.text import clean_text

GUIA_DE_GRADO = "https://www.unc.edu.ar/acad%C3%A9micas/guia-de-carreras-de-grado-0"
GUIA_DE_PREGRADO = "https://www.unc.edu.ar/acad%C3%A9micas/carreras-de-pregrado-de-la-unc-0"


@dataclass(frozen=True)
class CarreraDeLaGuia:
    nombre: str
    unidad: str
    tipo_unidad: str
    url: str
    nivel: str
    # The campus the guide lists the career at, when it lists campuses.
    sede: str | None = None


# "Contador/a Público/a": the guide writes both genders; the catalogue names
# the career once, as the other universities do.
_GENERO = re.compile(r"/(?:as?|os?)\b")


def nombre_de_la_carrera(texto: str) -> str:
    return clean_text(_GENERO.sub("", texto))


def tipo_de_unidad(nombre: str) -> str:
    # The pregrado careers of the Colegio Monserrat and the Escuela Superior
    # de Comercio Manuel Belgrano are taught by those schools of the
    # university: the schema's nearest kind of unit is a school.
    return "Escuela" if nombre.lower().startswith(("escuela", "colegio")) else "Facultad"


def leer_guia(html: str, pagina: str, nivel: str) -> list[CarreraDeLaGuia]:
    """Each career the guide lists: its name, its unit and its page."""
    carreras = []
    for item in BeautifulSoup(html or "", "html.parser").select("div.carrera"):
        enlace = item.find("a", href=True)
        nombre = enlace.find("span") if enlace else None
        if not enlace or not nombre:
            continue
        # The unit follows the name in the link ("Abogacía | Facultad de
        # Derecho"); the pregrado guide puts it instead in the heading above
        # a group of careers ("Colegio Nacional de Monserrat").
        unidad = clean_text(enlace.get_text(" ").replace(nombre.get_text(" "), "", 1)).strip(" |")
        if not unidad:
            encabezado = item.find_previous("h2")
            unidad = clean_text(encabezado.get_text(" ")) if encabezado else ""
        titulo = nombre_de_la_carrera(nombre.get_text(" ").strip(" |"))
        if not titulo or not unidad:
            continue
        carreras.append(CarreraDeLaGuia(titulo, unidad, tipo_de_unidad(unidad),
                                        urljoin(pagina, enlace["href"].strip()), nivel))
    return carreras


# --- Universidad Nacional de Río Cuarto ------------------------------------
#
# Río Cuarto lists its careers on one page, under the name of each faculty
# as the site abbreviates it ("Cs. Económicas"), in capitals:
#
#     <li><h3><strong>Cs. Económicas</strong></h3></li>
#     <ul><li><a href="https://www.eco.unrc.edu.ar/contador-publico/">CONTADOR PÚBLICO</a></li>

GUIA_UNRC = "https://www.unrc.edu.ar/unrc/estudiar/carreras.php"
_PREGRADO = re.compile(r"(?i)^(?:tecnicatura|t[ée]cnic[oa]|analista)\b")
# A completion cycle ("LICENCIATURA EN EDUCACIÓN FÍSICA -CICLO-") takes a
# student who already holds a degree: not a career to start.
_CICLO = re.compile(r"(?i)\bciclo\b")


def _facultad_unrc(texto: str) -> str:
    return "Facultad de " + clean_text(re.sub(r"\bCs\.\s*", "Ciencias ", texto))


def leer_guia_unrc(html: str, pagina: str = GUIA_UNRC) -> list[CarreraDeLaGuia]:
    from rumbo_scraper.database.exportar_catalogo import _titulo

    soup = BeautifulSoup(html or "", "html.parser")
    lista = soup.find("ul", class_="list-unstyled")
    carreras: list[CarreraDeLaGuia] = []
    unidad = None
    for elemento in (lista.find_all(["h3", "a"]) if lista else []):
        if elemento.name == "h3":
            unidad = _facultad_unrc(elemento.get_text(" "))
            continue
        nombre = clean_text(elemento.get_text(" "))
        if not unidad or not elemento.get("href") or not nombre or _CICLO.search(nombre):
            continue
        titulo = _titulo(nombre)
        # The page links one career as "hhttps://..."; a doubled letter is
        # not an address of its own.
        href = re.sub(r"^h+ttp", "http", elemento["href"].strip())
        carreras.append(CarreraDeLaGuia(
            titulo, unidad, "Facultad", urljoin(pagina, href),
            "Pregrado" if _PREGRADO.match(titulo) else "Grado"))
    return carreras


# --- Universidad Provincial de Córdoba -------------------------------------
#
# The Provincial lists its careers by faculty and by regional campus, each
# an accordion item, and within it by kind under a heading: "Carreras de
# Grado", "Carreras de Grado y Pregrado", "Carreras de Pregrado
# (Universitario)". Beside them, under the same accordion, it lists what is
# not a university career of its own: "Trayectos Preuniversitarios" and
# "Carreras Superiores (No Universitario)", taught at the provincial higher
# institutes its regional campuses host, and its postgraduates, which the
# catalogue reads apart. Those are left out.
#
# A faculty's careers are taught in the city of Córdoba, at buildings the
# page does not tie to each faculty; a regional campus's, at that campus.

GUIA_UPC = "https://www.upc.edu.ar/carrerasupc/"
SEDE_UPC = "Córdoba Capital"
_TITULO_INTERMEDIO = re.compile(
    r"(?i)\s+(?:con|c/)\s+(?:titulaci[oó]n|t[ií]tulo)\s+intermedi.*$|\s+con\s+orientaci[oó]n\b.*$")
_ANEXO = re.compile(r"(?i)\s*\((?:extensi[oó]n\s+[aá]ulica|anexo)[^)]*\)?")
_CICLO_UPC = re.compile(r"(?i)ciclo de complementaci|\(ccc\)")
_SECCION = re.compile(r"(?i)^carreras de (grado y pregrado|grado|pregrado)")


def _sede_regional(texto: str) -> str:
    """'Sede Regional Bell Ville "Mariano Moreno"' -> 'Sede Regional Bell Ville'."""
    return clean_text(re.sub(r"[\"“”].*$", "", texto))


def leer_guia_upc(html: str, pagina: str = GUIA_UPC) -> list[CarreraDeLaGuia]:
    soup = BeautifulSoup(html or "", "html.parser")
    carreras: list[CarreraDeLaGuia] = []
    unidad, nivel = None, None
    for elemento in soup.find_all(True):
        clases = " ".join(elemento.get("class") or [])
        if "e-n-accordion-item-title-text" in clases:
            unidad, nivel = clean_text(elemento.get_text(" ")), None
            continue
        if elemento.name == "h2":
            seccion = _SECCION.match(clean_text(elemento.get_text(" ")))
            # "Carreras de Grado y Pregrado" is a licenciatura with a
            # tecnicatura on the way: a grado career.
            nivel = ({"pregrado": "Pregrado"}.get(seccion.group(1).lower(), "Grado")
                     if seccion else None)
            continue
        if elemento.name != "a" or "/carreras/" not in (elemento.get("href") or ""):
            continue
        texto = clean_text(elemento.get_text(" "))
        if not unidad or not nivel or not texto or _CICLO_UPC.search(texto):
            continue
        nombre = clean_text(_ANEXO.sub("", _TITULO_INTERMEDIO.sub("", texto))).rstrip(" :;,")
        regional = unidad.lower().startswith("sede regional")
        carreras.append(CarreraDeLaGuia(
            nombre, "" if regional else unidad,
            "Facultad" if unidad.lower().startswith("facultad") else "Instituto",
            urljoin(pagina, elemento["href"].strip()), nivel,
            _sede_regional(unidad) if regional else SEDE_UPC))
    return carreras


# --- The plans of the UNC's Facultad de Ciencias Exactas, Físicas y Naturales
#
# Each career page links its plans ("Plan de estudios 2005", "Plan de
# estudios 2025"), each a page that lists the subjects year by year, each
# with its official code:
#
#     Primer año
#     Primer cuatrimestre
#     (10-09800) Fundamentos de Programación
#
# The newest plan is the one a student starts today. The levelling course
# ("Nivelación") comes before the first year and is the entry course, not
# the plan.

_PLAN_CON_ANIO = re.compile(r"(?i)^plan de estudios?\s+(\d{4})\b")
_ANIO_DEL_PLAN = {"primer": 1, "segundo": 2, "tercer": 3, "cuarto": 4, "quinto": 5, "sexto": 6}
_ANIO = re.compile(r"(?i)^(primer|segundo|tercer|cuarto|quinto|sexto)\s+a[ñn]o$")
_CON_CODIGO = re.compile(r"^\(\d{2}-\d{4,6}\)\s+(.+)$")
_FIN_DEL_PLAN = re.compile(r"(?i)^(?:compartir|links útiles)$")


def plan_mas_nuevo(html: str, pagina: str) -> str | None:
    """The page of the newest plan a career page links."""
    planes = []
    for enlace in BeautifulSoup(html or "", "html.parser").find_all("a", href=True):
        anio = _PLAN_CON_ANIO.match(clean_text(enlace.get_text(" ")))
        if anio:
            planes.append((int(anio.group(1)), urljoin(pagina, enlace["href"].strip())))
    return max(planes)[1] if planes else None


def leer_plan_fcefyn(html: str) -> list[tuple[str, int]]:
    soup = BeautifulSoup(html or "", "html.parser")
    for parte in soup.find_all(["script", "style", "nav", "header", "footer"]):
        parte.decompose()
    cuerpo = soup.find("main") or soup.body
    materias: list[tuple[str, int]] = []
    anio = None
    for linea in (cuerpo.get_text("\n").split("\n") if cuerpo else []):
        linea = clean_text(linea)
        if _FIN_DEL_PLAN.match(linea):
            break
        encabezado = _ANIO.match(linea)
        if encabezado:
            anio = _ANIO_DEL_PLAN[encabezado.group(1).lower()]
            continue
        materia = _CON_CODIGO.match(linea)
        if materia and anio and materia.group(1) not in [m for m, _ in materias]:
            materias.append((clean_text(materia.group(1)), anio))
    return materias
