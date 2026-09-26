"""The careers of universities read from their own list of careers.

Each reader here takes the page a university publishes with its careers and
returns them as `CarreraDeLaGuia`: the name, the unit that teaches it, the
link to its page, the level and, when the list says them, the campus and
the years it takes. The list is the university's own; nothing is added to
it but what its markup plainly says (a faculty's name the site gives in
full elsewhere, a level read off "Tecnicatura"). Completion cycles, which a
student starts with a degree already, and postgraduate programmes are left
out.
"""

from __future__ import annotations

import json
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from rumbo_scraper.normalizers.text import clean_text
from rumbo_scraper.parsers.unc import CarreraDeLaGuia

_PREGRADO = re.compile(r"(?i)^(?:tecnicatura|t[ée]cnic[oa]s?|analista|enfermer[oa]s?\b(?! universitari)|"
                       r"enfermer[ií]a universitaria|martillero|corredor|gu[ií]a|int[ée]rprete|"
                       r"bachiller|asistente|auxiliar|operador|perito|diplomado|productor|"
                       r"acompa[ñn]ante)")
_CICLO = re.compile(r"(?i)\bciclo\b|\bccc\b|complementaci[oó]n curricular|^\*")
_DURACION = re.compile(r"(?i)(\d+(?:[.,]\d)?)\s*(y\s+medio)?\s*a[ñn]os?(\s+y\s+medio)?")


def nivel(nombre: str) -> str:
    return "Pregrado" if _PREGRADO.match(nombre) else "Grado"


def es_ciclo(nombre: str) -> bool:
    return bool(_CICLO.search(nombre))


def anios(texto: str | None) -> float | None:
    """"5 años", "4 años y medio", "2 y medio años" -> years; None if none."""
    encontrado = _DURACION.search(texto or "")
    if not encontrado:
        return None
    valor = float(encontrado.group(1).replace(",", "."))
    valor += 0.5 if encontrado.group(2) or encontrado.group(3) else 0
    return valor if 1 <= valor <= 8 else None


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html or "", "html.parser")


def _texto(elemento) -> str:
    return clean_text(elemento.get_text(" ")) if elemento else ""


def _tipo(unidad: str) -> str:
    clave = unidad.lower()
    for prefijo, tipo in (("facultad", "Facultad"), ("escuela", "Escuela"), ("instituto", "Instituto"),
                          ("departamento", "Departamento"), ("centro", "Centro"),
                          ("asentamiento", "Centro"), ("sede", "Centro")):
        if clave.startswith(prefijo):
            return tipo
    return "Facultad"


def _carrera(nombre: str, unidad: str, url: str, sede: str | None = None,
             duracion: float | None = None, nivel_dicho: str | None = None) -> CarreraDeLaGuia | None:
    nombre = clean_text(nombre).strip(" *-–")
    if not nombre or es_ciclo(nombre):
        return None
    return CarreraDeLaGuia(nombre, unidad, _tipo(unidad) if unidad else "Facultad", url,
                           nivel_dicho or nivel(nombre), sede, duracion)


# --- Universidad Autónoma de Entre Ríos ------------------------------------
# ingresantes.uader.edu.ar lists every career as a card: its kind ("Tecnicatura")
# over its name ("Acuicultura"), its campuses and its faculty's acronym, which
# uader.edu.ar gives in full.

UADER = "https://ingresantes.uader.edu.ar/que-estudiar"
_FACULTADES_UADER = {
    "FCYT": "Facultad de Ciencia y Tecnología",
    "FCG": "Facultad de Ciencias de la Gestión",
    "FCVYS": "Facultad de Ciencias de la Vida y la Salud",
    "FHAYCS": "Facultad de Humanidades, Artes y Ciencias Sociales",
}


def leer_uader(html: str, pagina: str = UADER) -> list[CarreraDeLaGuia]:
    carreras = []
    for tarjeta in _soup(html).select("fieldset"):
        enlace = tarjeta.find("a", href=True)
        tipo, nombre, sigla = tarjeta.find("em"), tarjeta.find("h2"), tarjeta.find("p")
        if not enlace or not tipo or not nombre:
            continue
        texto = _texto(tarjeta)
        sedes = re.search(r"Sedes:\s*(.+?)\s*(?:FCyT|FCG|FCVyS|FHAyCS|$)", texto)
        unidad = _FACULTADES_UADER.get(_texto(sigla).upper(), "")
        titulo = f"{_texto(tipo)} en {_texto(nombre)}"
        url = urljoin(pagina, enlace["href"])
        for sede in ([clean_text(s) for s in sedes.group(1).split(",")] if sedes else [None]):
            carrera = _carrera(titulo, unidad, url, sede or None)
            if carrera:
                carreras.append(carrera)
    return carreras


# --- Universidad Nacional del Comahue ---------------------------------------
# uncoma.edu.ar/niveles/grado/ and /niveles/pre-grado/ list every career as a
# card, its campus, faculty and duration only in the card's classes
# ("ubicaciones-zapala-neuquen", "duracion-de-5-anos"). The career's page says
# the unit and the town in full; the list gives the name and link.

COMAHUE_GRADO = "https://uncoma.edu.ar/niveles/grado/"
COMAHUE_PREGRADO = "https://uncoma.edu.ar/niveles/pre-grado/"


def leer_comahue(html: str, pagina: str, traer=None) -> list[CarreraDeLaGuia]:
    carreras = []
    for item in _soup(html).select("div.e-loop-item"):
        clases = " ".join(item.get("class") or [])
        titulo = item.select_one("h3.elementor-flip-box__layer__title")
        enlace = item.select_one("a.elementor-flip-box__button[href]")
        if not titulo or not enlace:
            continue
        duracion = re.search(r"duracion-de-(\d+)(-y-medio)?-anos", clases)
        nivel_dicho = "Pregrado" if "niveles-pre-grado" in clases or "niveles-pregrado" in clases else "Grado"
        unidad, sede = "", None
        if traer:
            detalle = _texto(_soup(traer(enlace["href"])).find("main") or _soup(traer(enlace["href"])))
            encontrada = re.search(r"((?:Facultad|Asentamiento|Centro Regional|Escuela|Instituto)"
                                   r"[^:\n]{3,90}?)\s+Ciudad:\s*[–-]?\s*([A-ZÁÉÍÓÚÑ][^,]{2,40}),", detalle)
            if encontrada:
                unidad, sede = clean_text(encontrada.group(1)), clean_text(encontrada.group(2))
        carrera = _carrera(_texto(titulo), unidad, enlace["href"], sede,
                           (int(duracion.group(1)) + (0.5 if duracion.group(2) else 0)) if duracion else None,
                           nivel_dicho)
        if carrera:
            carreras.append(carrera)
    return carreras


# --- Universidad Nacional de Tierra del Fuego ------------------------------
# One page, careers under "Carreras de pregrado" / "Carreras de grado", each a
# list item with its campuses in parentheses ("(Sedes Ushuaia y Rio Grande)").
# A star marks a completion cycle.

UNTDF = "https://www.untdf.edu.ar/estudia-en-la-untdf/"


def leer_untdf(html: str, pagina: str = UNTDF) -> list[CarreraDeLaGuia]:
    carreras = []
    for encabezado in _soup(html).find_all("h3"):
        texto = _texto(encabezado).lower()
        if not texto.startswith("carreras de"):
            continue
        nivel_dicho = "Pregrado" if "pregrado" in texto else "Grado"
        lista = encabezado.find_next_sibling("ul")
        for item in (lista.find_all("li") if lista else []):
            enlace = item.find("a", href=True)
            linea = _texto(item).replace("Ver+", "").strip()
            sedes = re.search(r"\(Sedes?\s+([^)]*)\)", linea)
            nombre = re.sub(r"\s*\(Sedes?[^)]*\)", "", linea)
            if not enlace or linea.startswith("*"):
                continue
            for sede in re.split(r"\s+y\s+|,\s*", sedes.group(1)) if sedes else [None]:
                carrera = _carrera(nombre, "", urljoin(pagina, enlace["href"]),
                                   clean_text(sede) if sede else None, None, nivel_dicho)
                if carrera:
                    carreras.append(carrera)
    return carreras


# --- Universidad de Mendoza --------------------------------------------------
# The mega-menu on every page lists each faculty (its heading links the
# faculty) and its careers (menu items of the kind "carreras").

UM_MENDOZA = "https://um.edu.ar/"


def leer_um_mendoza(html: str, pagina: str = UM_MENDOZA) -> list[CarreraDeLaGuia]:
    carreras = []
    for titulo in _soup(html).select("h5.megamenu__menu_title"):
        unidad = _texto(titulo)
        contenedor = titulo.find_next_sibling()
        if not contenedor:
            continue
        for item in contenedor.select("li.menu-item-object-carreras > a[href]"):
            carrera = _carrera(_texto(item), f"Facultad de {unidad}" if not unidad.lower().startswith("facultad") else unidad,
                               item["href"])
            if carrera:
                carreras.append(carrera)
    return carreras


# --- Universidad CAECE ---------------------------------------------------------
# The mega-menu's collection is in the page, hidden: each item names the
# career, its slugs for the presencial and distance pages, its kind (Grado,
# Pregrado, Ciclo de grado, Posgrado...) and its department.

CAECE = "https://www.ucaece.edu.ar/carreras"


def leer_caece(html: str, pagina: str = CAECE) -> list[CarreraDeLaGuia]:
    carreras = []
    for item in _soup(html).select("div.nav-menu-desplegable-item"):
        nombre = item.find("a")
        tipo = item.select_one(".menu-slug-tipo")
        presencial = item.select_one(".menu-slug-presencial")
        distancia = item.select_one(".menu-slug-distancia")
        departamento = next((d for d in item.find_all("div")
                             if "departamento" in " ".join(d.get("class") or [])), None)
        tipo_texto = _texto(tipo)
        if not nombre or tipo_texto not in ("Grado", "Pregrado"):
            continue
        slug = _texto(presencial) or _texto(distancia)
        if not slug:
            continue
        unidad = _texto(departamento)
        carrera = _carrera(_texto(nombre), f"Departamento de {unidad}" if unidad and not unidad.lower().startswith("departamento") else unidad,
                           urljoin(pagina, f"/carrera/{slug}"), None, None, tipo_texto)
        if carrera:
            carreras.append(carrera)
    return carreras


# --- Universidad Champagnat -----------------------------------------------------
# The home lists each faculty as a card, its careers as links under it.

CHAMPAGNAT = "https://www.uch.edu.ar/"


def leer_champagnat(html: str, pagina: str = CHAMPAGNAT, traer=None) -> list[CarreraDeLaGuia]:
    # The home names each career by its degree, in lower case ("licenciado en
    # comercio internacional"); the career's own page heads it by its name.
    carreras = []
    for tarjeta in _soup(html).select("div.card"):
        titulo = tarjeta.select_one("h3.card-title")
        if not titulo:
            continue
        unidad = _texto(titulo)
        for enlace in tarjeta.select("a.nav-link[href*='/carrera/']"):
            nombre = _texto(enlace)
            if traer:
                encabezado = _soup(traer(enlace["href"])).find("h1")
                nombre = _texto(encabezado) or nombre
            nombre = nombre[:1].upper() + nombre[1:]
            carrera = _carrera(nombre, unidad, enlace["href"])
            if carrera:
                carreras.append(carrera)
    return carreras


# --- Instituto Universitario de Ciencias Biomédicas de Córdoba -------------------
# One page per level; each career a card with its duration.

IUCBC_GRADO = "https://www.iucbc.edu.ar/carreras-de-grado.html"
IUCBC_PREGRADO = "https://www.iucbc.edu.ar/pregrado.html"


def leer_iucbc(html: str, pagina: str) -> list[CarreraDeLaGuia]:
    carreras = []
    for item in _soup(html).select("div.item-oferta"):
        titulo = item.select_one(".item-oferta-titulo h3")
        enlace = item.select_one(".item-oferta-boton a[href]")
        duracion = None
        for caracteristica in item.select(".item-caracteristica"):
            if "duraci" in _texto(caracteristica.select_one(".item-caracteristica-titulo")).lower():
                duracion = anios(_texto(caracteristica.select_one(".item-caracteristica-descripcion")))
        if not titulo or not enlace:
            continue
        carrera = _carrera(_texto(titulo), "", urljoin(pagina, enlace["href"]), None, duracion,
                           "Pregrado" if "pregrado" in pagina else None)
        if carrera:
            carreras.append(carrera)
    return carreras


# --- Universidad Nacional de Río Tercero -----------------------------------------
# Each school's heading, then a card per career linking /oferta-academica/.

UNRT = "https://unrt.edu.ar/propuesta-academica/"


def leer_unrt(html: str, pagina: str = UNRT, traer=None) -> list[CarreraDeLaGuia]:
    # Each career's page has a table of general data: the unit, the career,
    # its level and its years. The list only links them.
    enlaces = []
    for enlace in _soup(html).find_all("a", href=True):
        if "/oferta-academica/" in enlace["href"] and enlace["href"] not in enlaces:
            enlaces.append(enlace["href"])
    carreras = []
    for url in enlaces if traer else []:
        datos = {_texto(fila.find("th") or fila.find("td")): _texto(fila.find_all(["th", "td"])[-1])
                 for fila in _soup(traer(url)).find_all("tr") if len(fila.find_all(["th", "td"])) >= 2}
        carrera = _carrera(datos.get("Carrera", ""), datos.get("Unidad Académica", ""), url, None,
                           anios(datos.get("Años de duración")),
                           datos.get("Nivel de la carrera") if datos.get("Nivel de la carrera") in ("Grado", "Pregrado") else None)
        if carrera:
            carreras.append(carrera)
    return carreras


# --- Universidad Nacional Madres de Plaza de Mayo ---------------------------------
# The careers are the items of the home's "Carreras" menu.

UNMA = "https://unma.edu.ar/"


def leer_unma(html: str, pagina: str = UNMA) -> list[CarreraDeLaGuia]:
    menu = _soup(html).select_one("ul[aria-labelledby=carrerasDropdown]")
    carreras = []
    for enlace in (menu.select("a.dropdown-item[href]") if menu else []):
        nombre = re.sub(r"^Lic\.\s+", "Licenciatura ", re.sub(r"^Prof\.\s+", "Profesorado ", _texto(enlace)))
        carrera = _carrera(nombre, "", urljoin(pagina, enlace["href"]))
        if carrera:
            carreras.append(carrera)
    return carreras


# --- Universidad Maimónides -----------------------------------------------------
# The list is data in the page: DATA = {facultad: {label, pregrado: [[name,
# url]], grado: [...]}}. The intermediate titles point at the licenciatura's
# page and are not careers of their own.

MAIMONIDES = "https://www.maimonides.edu/carreras/"


def leer_maimonides(html: str, pagina: str = MAIMONIDES) -> list[CarreraDeLaGuia]:
    # L2_DATA is the list as JSON: {"f": faculty key, "n": level, "t": name,
    # "u": page, "i": whether it is an intermediate title}. DATA names each
    # faculty key ("salud: {label: \"Facultad de Ciencias de la Salud\"").
    datos = re.search(r"var\s+L2_DATA\s*=\s*(\[.*?\])\s*;", html or "", re.S)
    if not datos:
        return []
    try:
        entradas = json.loads(re.sub(r",\s*([}\]])", r"\1", datos.group(1)))
    except ValueError:
        return []
    etiquetas = dict(re.findall(r"(\w+):\s*\{\s*label:\s*\"([^\"]+)\"", html))
    carreras, urls = [], set()
    for entrada in entradas:
        if entrada.get("i") or entrada.get("n") not in ("pregrado", "grado") or entrada.get("u") in urls:
            continue
        urls.add(entrada.get("u"))
        carrera = _carrera(entrada.get("t") or "", etiquetas.get(entrada.get("f"), ""),
                           urljoin(pagina, entrada.get("u") or ""), None, None,
                           "Pregrado" if entrada["n"] == "pregrado" else "Grado")
        if carrera:
            carreras.append(carrera)
    return carreras


# --- Universidad Evangélica ------------------------------------------------------
# A call-to-action per career; its button says "Ver carrera" (a diploma or a
# chaplaincy says otherwise).

UEVANGELICA = "https://uevangelica.edu.ar/oferta-academica/"


def leer_uevangelica(html: str, pagina: str = UEVANGELICA) -> list[CarreraDeLaGuia]:
    carreras = []
    for titulo in _soup(html).select("h3.elementor-cta__title"):
        boton = titulo.find_next("a", class_="elementor-cta__button")
        if not boton or "ver carrera" not in _texto(boton).lower():
            continue
        carrera = _carrera(_texto(titulo), "", boton["href"])
        if carrera:
            carreras.append(carrera)
    return carreras


# --- Universidad Católica de las Misiones ---------------------------------------
# The "CARRERAS" menu groups careers under each faculty's heading.

UCAMI = "https://www.ucami.edu.ar/"


def leer_ucami(html: str, pagina: str = UCAMI) -> list[CarreraDeLaGuia]:
    carreras = []
    for encabezado in _soup(html).find_all("h4"):
        unidad = _texto(encabezado)
        if not unidad.lower().startswith("facultad"):
            continue
        lista = encabezado.find_next_sibling("ul")
        for enlace in (lista.find_all("a", href=True) if lista else []):
            carrera = _carrera(_texto(enlace), unidad, urljoin(pagina, enlace["href"].strip()))
            if carrera:
                carreras.append(carrera)
    return carreras


# --- Instituto Universitario de Seguridad Marítima --------------------------------
# One tab per level (#pregrado, #grado, #ciclo, #posgrado); each career with its
# duration. Its page is reached by a form, so the link is the list.

IUSM = "https://iusm.edu.ar/page/carreras.php"


def leer_iusm(html: str, pagina: str = IUSM) -> list[CarreraDeLaGuia]:
    carreras = []
    for pestania, nivel_dicho in (("pregrado", "Pregrado"), ("grado", "Grado")):
        panel = _soup(html).find(id=pestania)
        for titulo in (panel.find_all("h4") if panel else []):
            bloque = titulo.find_parent("div")
            carrera = _carrera(_texto(titulo).title() if _texto(titulo).isupper() else _texto(titulo),
                               "", pagina, None, anios(_texto(bloque)), nivel_dicho)
            if carrera:
                carreras.append(carrera)
    return carreras
