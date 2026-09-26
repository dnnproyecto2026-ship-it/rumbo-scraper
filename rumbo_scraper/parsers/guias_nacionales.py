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


# The abbreviations a menu writes a degree with ("Lic. en Podología", "Tec. Univ.
# en ...", "Prof. de ...", "Ing. ..."), written out.
_ABREVIATURAS = (
    (re.compile(r"^Lic\.\s*(?:en\s+)?", re.I), "Licenciatura en "),
    (re.compile(r"^Tec\.\s*Univ\.\s*(?:en\s+)?", re.I), "Tecnicatura Universitaria en "),
    (re.compile(r"^Tec\.\s*(?:en\s+)?", re.I), "Tecnicatura en "),
    (re.compile(r"^Prof\.\s*(?=(?:de|en)\s)", re.I), "Profesorado "),
    (re.compile(r"^Prof\.\s*", re.I), "Profesorado en "),
    (re.compile(r"^Ing\.\s*(?:en\s+)?", re.I), "Ingeniería en "),
)


def expandir(nombre: str) -> str:
    for patron, completo in _ABREVIATURAS:
        if patron.match(nombre):
            return clean_text(patron.sub(completo, nombre, count=1))
    return nombre


def _carrera(nombre: str, unidad: str, url: str, sede: str | None = None,
             duracion: float | None = None, nivel_dicho: str | None = None) -> CarreraDeLaGuia | None:
    nombre = expandir(clean_text(nombre).strip(" *-–"))
    # The way it is taught is the offer's, not the career's name.
    nombre = re.sub(r"(?i)\s*[-–(]?\s*(?:modalidad\s+)?(?:a\s+)?(?:distancia|presencial|virtual|semipresencial|h[ií]brida)\)?$", "", nombre)
    unidad = re.sub(r"\bCs\.\s*", "Ciencias ", unidad)
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


# --- Names written without accents ----------------------------------------------
# A university's system that prints names in capitals without accents
# ("INGENIERIA EN COMPUTACION") gets each word back as the catalogue already
# spells it in some career's name ("Ingeniería", "Computación"): only words
# that are the same letters but for the accents.

_VOCABULARIO: dict[str, str] | None = None
_MINUSCULAS = frozenset("de del la las los el y e en a al con para por o u".split())


def _vocabulario() -> dict[str, str]:
    global _VOCABULARIO
    if _VOCABULARIO is None:
        from collections import Counter
        from pathlib import Path

        from rumbo_scraper.normalizers.text import comparison_key

        formas: dict[str, Counter] = {}
        catalogo = Path("data/catalogo_depurado.json")
        if catalogo.exists():
            for universidad in json.loads(catalogo.read_text()).get("universidades") or []:
                for carrera in universidad["datos"].get("carreras") or []:
                    for palabra in re.findall(r"[A-Za-zÁÉÍÓÚÑáéíóúñÜü]+", carrera["nombre_carrera"]):
                        formas.setdefault(comparison_key(palabra), Counter())[palabra.lower()] += 1
        _VOCABULARIO = {clave: contador.most_common(1)[0][0] for clave, contador in formas.items()}
    return _VOCABULARIO


def con_tildes(nombre: str) -> str:
    """ "INGENIERIA EN COMPUTACION" -> "Ingeniería en Computación"."""
    from rumbo_scraper.normalizers.text import comparison_key

    vocabulario = _vocabulario()
    palabras = []
    for i, palabra in enumerate(clean_text(nombre).split()):
        base = vocabulario.get(comparison_key(palabra), palabra.lower())
        palabras.append(base if i and base in _MINUSCULAS else base[:1].upper() + base[1:])
    return " ".join(palabras)


def _titulo_si_mayusculas(nombre: str) -> str:
    return con_tildes(nombre) if nombre.isupper() else nombre


# --- Universidad Nacional del Centro de la Provincia de Buenos Aires ---------------
# Four pages (?page=0..3) of rows "Career - Campus"; a row per career and campus,
# with "(pase ...)" rows that are a transfer, not a career.

UNICEN = "https://www.unicen.edu.ar/content/estudios-de-grado?page={}"


def leer_unicen(html: str, pagina: str) -> list[CarreraDeLaGuia]:
    carreras = []
    for fila in _soup(html).select("div.views-row"):
        enlace = fila.select_one(".views-field-title a[href]")
        sede = _texto(fila.select_one(".views-field-title-1"))
        nombre = _texto(enlace)
        if not enlace or re.search(r"(?i)\(pase|ciclo final", nombre):
            continue
        carrera = _carrera(nombre, "", urljoin(pagina, enlace["href"]), sede or None)
        if carrera:
            carreras.append(carrera)
    return carreras


# --- Universidad Nacional del Sur ------------------------------------------------------
# The grado table: name (capitals, no accents), duration in terms, department.

UNS = "https://uns.edu.ar/secciones/academicas/carreras/oferta-academica_carreras-grado.php"


def leer_uns(html: str, pagina: str = UNS) -> list[CarreraDeLaGuia]:
    carreras = []
    for fila in _soup(html).select("tr.row_carrera"):
        enlace = fila.select_one("td.col_nombre a[href]")
        cuatrimestres = re.search(r"(\d+)", _texto(fila.select_one("td.col_dur")))
        departamento = _texto(fila.select_one("td.col_depto"))
        if not enlace:
            continue
        carrera = _carrera(con_tildes(_texto(enlace)),
                           f"Departamento de {departamento}" if departamento else "",
                           enlace["href"], "Bahía Blanca",
                           int(cuatrimestres.group(1)) / 2 if cuatrimestres else None)
        if carrera:
            carreras.append(carrera)
    return carreras


# --- Universidad Católica de Santiago del Estero -------------------------------------
# The mega-menu: columns headed "Grado" / "Pregrado" / "Posgrado", each career a
# link; the same career twice when also taught another way ("Híbrida", "A
# Distancia" in its subtitle).

UCSE = "https://www.ucse.edu.ar/carreras/"


def leer_ucse(html: str, pagina: str = UCSE) -> list[CarreraDeLaGuia]:
    carreras, nivel_actual, vistos = [], None, set()
    for elemento in _soup(html).select("span.quadmenu-title, li.quadmenu-item-level-2 > a[href]"):
        if elemento.name == "span":
            titulo = _texto(elemento).lower()
            nivel_actual = {"grado": "Grado", "pregrado": "Pregrado"}.get(titulo)
            continue
        if not nivel_actual:
            continue
        nombre = _texto(elemento.select_one(".quadmenu-text"))
        from rumbo_scraper.normalizers.text import comparison_key
        if not nombre or comparison_key(nombre) in vistos:
            continue
        vistos.add(comparison_key(nombre))
        nombre = con_tildes(nombre) if nombre.isascii() else nombre
        carrera = _carrera(nombre, "", elemento["href"], None, None, nivel_actual)
        if carrera:
            carreras.append(carrera)
    return carreras


# --- Universidad Nacional de Santiago del Estero -------------------------------------
# One page per level: each faculty in bold, its careers the links of the next
# paragraph ("– Ingeniería Agronómica"); "TI:" lines are intermediate titles.

UNSE_GRADO = "https://www.unse.edu.ar/carreras-de-grado/"
UNSE_PREGRADO = "https://www.unse.edu.ar/carreras-de-pregrado/"


def leer_unse(html: str, pagina: str) -> list[CarreraDeLaGuia]:
    carreras, unidad = [], ""
    nivel_dicho = "Pregrado" if "pregrado" in pagina else "Grado"
    for bloque in _soup(html).select("div.et_pb_text_inner"):
        for parrafo in bloque.find_all("p"):
            negrita = parrafo.find("strong")
            if negrita and _texto(negrita).lower().startswith(("facultad", "escuela", "instituto")):
                unidad = re.sub(r"\bCs\.\s*", "Ciencias ", _texto(negrita))
                continue
            for enlace in parrafo.find_all("a", href=True):
                nombre = _texto(enlace)
                if not unidad or not nombre.startswith(("–", "-")):
                    continue
                carrera = _carrera(nombre.lstrip("–- "), unidad, enlace["href"], None, None, nivel_dicho)
                if carrera:
                    carreras.append(carrera)
    return carreras


# --- Universidad Nacional de Río Negro -----------------------------------------------
# Grado (id=1) and short-cycle grado (id=5, tecnicaturas), grouped by campus
# (groupby=sede): each campus a heading, its careers under it, in capitals.

UNRN = "https://www.unrn.edu.ar/carreras.php?id={}&groupby=sede"


def leer_unrn(html: str, pagina: str) -> list[CarreraDeLaGuia]:
    carreras = []
    for grupo in _soup(html).select("div.carrera-listado div.carrera"):
        sede = _texto(grupo.select_one("div.tit")).title().replace("Sede ", "Sede ")
        for enlace in grupo.select("a.item[href]"):
            carrera = _carrera(_titulo_si_mayusculas(_texto(enlace.find("h4"))), "",
                               urljoin(pagina, enlace["href"]), sede or None, None,
                               "Pregrado" if "id=5" in pagina else None)
            if carrera:
                carreras.append(carrera)
    return carreras


# --- Universidad Nacional de Entre Ríos -------------------------------------------------
# estudia.uner.edu.ar/propuestas/, five pages; each proposal's title and its kind
# ("Carreras de Grado", "Carreras de Pregrado", ciclos, posgrado).

UNER = "https://estudia.uner.edu.ar/propuestas/page/{}/"


def leer_uner(html: str, pagina: str) -> list[CarreraDeLaGuia]:
    carreras = []
    for titulo in _soup(html).select("h1.elementor-heading-title a[href]"):
        # The kind is shown above the title, in the same card.
        info = titulo.find_previous("span", class_="elementor-post-info__item--type-custom")
        tipo = _texto(info).lower()
        if "carreras de grado" not in tipo and "carreras de pregrado" not in tipo:
            continue
        carrera = _carrera(_texto(titulo), "", titulo["href"], None, None,
                           "Pregrado" if "pregrado" in tipo else "Grado")
        if carrera:
            carreras.append(carrera)
    return carreras


# --- Universidad del Norte Santo Tomás de Aquino -----------------------------------------
# A tab per faculty ("Fac. de Economía y Administración"), inside it a "Carreras"
# tab with the careers as links, the campus as a suffix: (SC) Sede Central,
# (YB) Yerba Buena, (CUC) Concepción.

UNSTA = "https://www.unsta.edu.ar/oferta_academica/"
_SEDES_UNSTA = {"SC": "Sede Central", "YB": "Campus Yerba Buena", "CUC": "Campus Concepción"}


def leer_unsta(html: str, pagina: str = UNSTA) -> list[CarreraDeLaGuia]:
    soup = _soup(html)
    carreras = []
    exterior = soup.select_one("div.e-n-tabs")
    if not exterior:
        return []
    titulos = exterior.select(":scope > div.e-n-tabs-heading > button .e-n-tab-title-text")
    paneles = exterior.select(":scope > div.e-n-tabs-content > div[role=tabpanel]")
    for titulo, panel in zip(titulos, paneles):
        unidad = re.sub(r"^Fac\.\s*", "Facultad ", _texto(titulo))
        interno = panel.select_one("div.e-n-tabs")
        if not interno:
            continue
        nombres = [_texto(t) for t in interno.select(":scope > div.e-n-tabs-heading .e-n-tab-title-text")]
        subpaneles = interno.select(":scope > div.e-n-tabs-content > div[role=tabpanel]")
        for nombre_pestania, subpanel in zip(nombres, subpaneles):
            if nombre_pestania.lower() != "carreras":
                continue
            for enlace in subpanel.select("li a[href]"):
                texto = _texto(enlace)
                if "*" in texto or re.search(r"(?i)\bccc\b|distancia", texto):
                    continue
                sufijos = re.findall(r"\(([^)]*)\)", texto)
                nombre = clean_text(re.sub(r"\([^)]*\)", "", texto))
                sedes = [_SEDES_UNSTA[s.strip()] for suf in sufijos for s in suf.split("/") if s.strip() in _SEDES_UNSTA]
                for sede in sedes or [None]:
                    carrera = _carrera(nombre, unidad, enlace["href"], sede)
                    if carrera:
                        carreras.append(carrera)
    return carreras


# --- Universidad Provincial del Sudoeste --------------------------------------------------
# Headings "CARRERAS DE GRADO" / "CARRERAS DE PREGRADO" / "CARRERAS PROFESIONALES
# DE PREGRADO", each a list of links; a career listed per plan ("(Plan 2014)",
# "(Plan 2020)") is one career: the newest plan's link is kept.

UPSO = "https://www.upso.edu.ar/carreras/"


def leer_upso(html: str, pagina: str = UPSO) -> list[CarreraDeLaGuia]:
    carreras: dict[str, tuple[int, CarreraDeLaGuia]] = {}
    for encabezado in _soup(html).find_all("h5"):
        titulo = _texto(encabezado).lower()
        if "grado" not in titulo or "posgrado" in titulo:
            continue
        nivel_dicho = "Pregrado" if "pregrado" in titulo else "Grado"
        lista = encabezado.find_next_sibling("ul")
        for enlace in (lista.find_all("a", href=True) if lista else []):
            texto = _texto(enlace)
            plan = re.search(r"\(Plan (\d{4})\)", texto)
            nombre = clean_text(re.sub(r"\(Plan \d{4}\)", "", texto))
            carrera = _carrera(nombre, "", urljoin(pagina, enlace["href"]), None, None, nivel_dicho)
            anio = int(plan.group(1)) if plan else 0
            if carrera and (nombre not in carreras or anio > carreras[nombre][0]):
                carreras[nombre] = (anio, carrera)
    return [carrera for _, carrera in carreras.values()]


# --- Universidad del Gran Rosario ---------------------------------------------------------
# /carreras/?grado=grado and ?grado=pre-grado: a card per career.

UGR_GRADO = "https://ugr.edu.ar/carreras/?grado=grado"
UGR_PREGRADO = "https://ugr.edu.ar/carreras/?grado=pre-grado"


def leer_ugr(html: str, pagina: str) -> list[CarreraDeLaGuia]:
    carreras = []
    for tarjeta in _soup(html).select("div.card-carrera"):
        enlace = tarjeta.select_one(".card-carrera__title a[href]")
        if not enlace:
            continue
        carrera = _carrera(_texto(enlace), "", enlace["href"], None,
                           anios(_texto(tarjeta.select_one(".card-carrera__meta__length"))),
                           "Pregrado" if "pre-grado" in pagina else "Grado")
        if carrera:
            carreras.append(carrera)
    return carreras


# --- Universidad de la Cuenca del Plata ---------------------------------------------------
# A page per faculty; each career a card with its kind (Grado, Corta, Ciclo) and
# its duration.

UCP = ("https://www.ucp.edu.ar/facultades/facultad-de-ciencias-de-la-salud-y-bienestar/",
       "https://www.ucp.edu.ar/facultades/facultad-de-ciencias-economicas-y-ambientales/",
       "https://www.ucp.edu.ar/facultades/facultad-de-ciencias-juridicas-y-politicas/",
       "https://www.ucp.edu.ar/facultades/facultad-de-ciencias-sociales-y-humanidades/",
       "https://www.ucp.edu.ar/facultades/facultad-de-ingenieria-tecnologia-y-arquitectura/")


def leer_ucp(html: str, pagina: str) -> list[CarreraDeLaGuia]:
    soup = _soup(html)
    unidad = _texto(soup.find("h1")) or ""
    carreras = []
    for modulo in soup.select("div.facultad_carrera_modulo"):
        enlace = modulo.find_parent("a", href=True)
        tipo = _texto(modulo.select_one("div.tipo")).lower()
        if not enlace or tipo not in ("grado", "corta"):
            continue
        carrera = _carrera(_texto(modulo.find("h3")), unidad if unidad.lower().startswith("facultad") else "",
                           enlace["href"], None, anios(_texto(modulo.select_one(".duracion"))),
                           "Pregrado" if tipo == "corta" else "Grado")
        if carrera:
            carreras.append(carrera)
    return carreras


# --- Universidad Juan Agustín Maza ------------------------------------------------------
# "Todas las Carreras": a card per career, a link per campus it is taught at.

UMAZA = "https://www.umaza.edu.ar/ingresoumaza"


def leer_umaza(html: str, pagina: str = UMAZA) -> list[CarreraDeLaGuia]:
    carreras = []
    for tarjeta in _soup(html).select("div.card"):
        titulo = tarjeta.select_one("h5.card-title")
        if not titulo:
            continue
        for enlace in tarjeta.select("p.card-text a[href]"):
            lugar = _texto(enlace)
            sede = None if re.search(r"(?i)distancia|virtual", lugar) else lugar
            carrera = _carrera(_texto(titulo), "", urljoin(pagina, enlace["href"]), sede)
            if carrera:
                carreras.append(carrera)
    return carreras


# --- Universidad de la Marina Mercante ----------------------------------------------------
# A page per faculty, each career a button.

UDEMM = ("https://www.udemm.edu.ar/carreras/facultad-de-administracion-y-economia/",
         "https://www.udemm.edu.ar/carreras/cs-juridicas-sociales-y-de-la-comunicacion/",
         "https://www.udemm.edu.ar/carreras/humanidades/",
         "https://www.udemm.edu.ar/carreras/ingenieria/")


def leer_udemm(html: str, pagina: str) -> list[CarreraDeLaGuia]:
    soup = _soup(html)
    unidad = next((_texto(h) for h in soup.find_all(["h1", "h2", "h3"])
                   if _texto(h).lower().startswith("facultad")), "")
    carreras = []
    for enlace in soup.select("a.ubtn-link[href]"):
        if "/carreras/" not in enlace["href"]:
            continue
        carrera = _carrera(_texto(enlace.select_one(".ubtn-text")), unidad, enlace["href"])
        if carrera:
            carreras.append(carrera)
    return carreras


# --- Universidad Católica de Santa Fe -------------------------------------------------------
# Each faculty's heading and the list of its careers; the postgraduate
# department is left out, and cycles carry " – CCC".

UCSF = "https://www.ucsf.edu.ar/carreras/"


def leer_ucsf(html: str, pagina: str = UCSF) -> list[CarreraDeLaGuia]:
    carreras = []
    for grupo in _soup(html).select("div.row.fc"):
        encabezado = _texto(grupo.find("h3")).rstrip(": ")
        if "posgrado" in encabezado.lower():
            continue
        unidad = encabezado if encabezado.lower().startswith(("facultad", "escuela", "instituto")) \
            else f"Facultad de {encabezado}"
        for enlace in grupo.select("li.cr a[href]"):
            carrera = _carrera(_texto(enlace), unidad, enlace["href"])
            if carrera:
                carreras.append(carrera)
    return carreras


# --- Instituto Universitario Patagónico de las Artes ------------------------------------------
# An article per career, its department above it; the introductory music
# courses and the postgraduate ones are left out.

IUPA = "https://iupa.edu.ar/oferta-universitaria/"


def leer_iupa(html: str, pagina: str = IUPA) -> list[CarreraDeLaGuia]:
    carreras = []
    for articulo in _soup(html).select("article.type-carreras"):
        clases = " ".join(articulo.get("class") or [])
        if "posgrado" in clases or "investigacion" in clases:
            continue
        titulo = articulo.select_one("header a[href]")
        departamento = _texto(articulo.find("h2"))
        if not titulo:
            continue
        carrera = _carrera(_texto(titulo), f"Departamento de {departamento}" if departamento else "",
                           titulo["href"])
        if carrera:
            carreras.append(carrera)
    return carreras


# --- Universidad Adventista del Plata ---------------------------------------------------------
# The navigation menu: each faculty (a page under /carreras/<faculty>/) and its
# careers under it. The Instituto Superior (tertiary, not university), the
# pre-university courses and postgraduates are left out.

UAP = "https://uap.edu.ar/carreras/"
_UAP_FUERA = re.compile(r"(?i)instituto superior|preuniversitario|posgrado")


def leer_uap(html: str, pagina: str = UAP) -> list[CarreraDeLaGuia]:
    carreras, vistas = [], set()
    for item in _soup(html).select("li.menu-item-has-children"):
        enlace = item.find("a", href=True, recursive=False)
        if not enlace or not re.search(r"/carreras/[^/]+/?$", enlace["href"]) or _UAP_FUERA.search(_texto(enlace)):
            continue
        unidad = f"Facultad de {_texto(enlace)}"
        for hijo in item.select(":scope > ul > li > a[href]"):
            if hijo["href"] in vistas:
                continue
            vistas.add(hijo["href"])
            carrera = _carrera(_texto(hijo), unidad, hijo["href"])
            if carrera:
                carreras.append(carrera)
    return carreras


# --- Universidad Atlántida Argentina ---------------------------------------------------------
# Every card is in the page and filtered in the browser by its data: the
# program (grado, pre-grado, cycles, postgraduates...), the faculty and the
# campuses.

ATLANTIDA = "https://inscribite.atlantida.edu.ar/carreras/"
_SEDES_ATLANTIDA = {"mar-de-ajo": "Mar de Ajó", "dolores": "Dolores", "mar-del-plata": "Mar del Plata",
                    "pinamar": "Pinamar", "san-bernardo": "San Bernardo", "villa-gesell": "Villa Gesell"}


def leer_atlantida(html: str, pagina: str = ATLANTIDA) -> list[CarreraDeLaGuia]:
    carreras = []
    for tarjeta in _soup(html).select("article.ua-card-career"):
        programa = tarjeta.get("data-program") or ""
        if programa not in ("grado", "pre-grado"):
            continue
        titulo = tarjeta.select_one("h3.ua-card-title")
        # The card opens the career's page; its button, the faculty's.
        destino = re.search(r"location\.href\s*=\s*'\s*([^']+?)\s*'", tarjeta.get("onclick") or "")
        url = destino.group(1) if destino else pagina
        nombre = re.sub(r"(?i)\s+(?:presencial|a distancia|virtual|semipresencial)$", "", _texto(titulo))
        sedes = [_SEDES_ATLANTIDA.get(s.strip()) for s in (tarjeta.get("data-campus") or "").split(",")]
        for sede in [s for s in sedes if s] or [None]:
            carrera = _carrera(nombre, "", url, sede, None,
                               "Pregrado" if programa == "pre-grado" else "Grado")
            if carrera:
                carreras.append(carrera)
    return carreras


# --- Universidad Nacional de la Patagonia San Juan Bosco ----------------------------------------
# "Todas las carreras": each faculty's heading, each career an image whose
# text says it all: "Licenciatura en Historia: 5 años, Presencial, Comodoro
# Rivadavia y Trelew".

UNP = "https://www.unp.edu.ar/vivilauni/index.php?option=com_content&view=article&id=122&Itemid=239&lang=es"


def leer_unp(html: str, pagina: str = UNP) -> list[CarreraDeLaGuia]:
    carreras, unidad = [], ""
    for elemento in _soup(html).find_all(["strong", "img"]):
        if elemento.name == "strong":
            texto = _texto(elemento)
            if texto.lower().startswith(("facultad", "escuela", "instituto")):
                unidad = texto
            continue
        alt = clean_text(elemento.get("alt") or "")
        partes = alt.split(":", 1)
        enlace = elemento.find_parent("a", href=True)
        if len(partes) < 2 or not enlace or not unidad:
            continue
        datos = [clean_text(p) for p in partes[1].split(",")]
        lugares = ", ".join(d for d in datos if not re.search(r"(?i)a[ñn]os|presencial|distancia", d))
        for sede in [clean_text(s) for s in re.split(r"\s+y\s+|,\s*", lugares) if clean_text(s)] or [None]:
            carrera = _carrera(partes[0], unidad, enlace["href"], sede, anios(partes[1]))
            if carrera:
                carreras.append(carrera)
    return carreras


# --- Universidad Nacional de Rafaela ------------------------------------------------------------
# A page per kind (tecnicaturas, licenciaturas e ingeniería); each career an
# image card whose alt is a short name. The career's page says the full one
# ("Nombre de la propuesta formativa:") and its duration.

UNRAF = ("https://unraf.edu.ar/que-estudio/tecnicaturas",
         "https://unraf.edu.ar/que-estudio/licenciaturas-e-ingenieria")


def leer_unraf(html: str, pagina: str, traer=None) -> list[CarreraDeLaGuia]:
    carreras = []
    for tarjeta in _soup(html).select("a.carrera-card[href]"):
        url = urljoin(pagina, tarjeta["href"])
        nombre, duracion = clean_text((tarjeta.find("img") or {}).get("alt") or ""), None
        if traer:
            texto = _texto(_soup(traer(url)))
            completo = re.search(r"Nombre de la propuesta formativa:\s*(.+?)\s+(?:T[íi]tulo|Nivel|Duraci)", texto)
            nombre = clean_text(completo.group(1)) if completo else nombre
            duracion = anios(re.search(r"Duraci[óo]n:\s*([^.]{0,40})", texto).group(1)) \
                if re.search(r"Duraci[óo]n:\s*([^.]{0,40})", texto) else None
        carrera = _carrera(nombre, "", url, None, duracion,
                           "Pregrado" if "tecnicaturas" in pagina else None)
        if carrera:
            carreras.append(carrera)
    return carreras


# --- Instituto Universitario de la Policía Federal Argentina ---------------------------------------
# Buttons per career (c_*.html); completion cycles are cl_*.html.

IUPFA = "https://universidad-policial.edu.ar/carreras.html"


def leer_iupfa(html: str, pagina: str = IUPFA) -> list[CarreraDeLaGuia]:
    carreras, vistas = [], set()
    for enlace in _soup(html).select("a.button[href]"):
        if not enlace["href"].startswith("c_") or enlace["href"] in vistas:
            continue
        vistas.add(enlace["href"])
        carrera = _carrera(_titulo_si_mayusculas(_texto(enlace)), "", urljoin(pagina, enlace["href"]))
        if carrera:
            carreras.append(carrera)
    return carreras


# --- Small institutes: a menu or a grid of cards -------------------------------------------------

IUDPT = "https://iudpt.edu.ar/carreras/"
IUCE = "https://i-uce.edu.ar/"
EUT = "https://eut.edu.ar/carreras/"
IUYMCA = "https://iuymca.edu.ar/"
USBA = "https://usba.edu.ar/"
UDE = "https://www.ude.edu.ar/"


def leer_iudpt(html: str, pagina: str = IUDPT) -> list[CarreraDeLaGuia]:
    carreras, vistas = [], set()
    for enlace in _soup(html).select("a.mega-menu-link[href*='/oferta-academica/']"):
        if enlace["href"] in vistas:
            continue
        vistas.add(enlace["href"])
        carrera = _carrera(_texto(enlace), "", enlace["href"])
        if carrera:
            carreras.append(carrera)
    return carreras


def leer_iuce(html: str, pagina: str = IUCE) -> list[CarreraDeLaGuia]:
    carreras = []
    for enlace in _soup(html).select("a[href^='/careers/']"):
        carrera = _carrera(_texto(enlace.select_one("h3.name-degree")), "", urljoin(pagina, enlace["href"]))
        if carrera:
            carreras.append(carrera)
    return carreras


def leer_eut(html: str, pagina: str = EUT) -> list[CarreraDeLaGuia]:
    carreras, vistas = [], set()
    for enlace in _soup(html).select("h3.elementor-heading-title a[href*='/carrera/']"):
        nombre = clean_text(re.sub(r"\((?:presencial|a distancia)\)", "", _texto(enlace), flags=re.I))
        nombre = _titulo_si_mayusculas(nombre)
        if nombre.lower() in vistas:
            continue
        vistas.add(nombre.lower())
        carrera = _carrera(nombre, "", enlace["href"])
        if carrera:
            carreras.append(carrera)
    return carreras


def _menu(html: str, rotulo: str) -> list:
    for item in _soup(html).select("li.menu-item-has-children"):
        enlace = item.find("a", recursive=False)
        if enlace and _texto(enlace).lower() == rotulo:
            return item.select("ul.sub-menu a[href]")
    return []


def leer_iuymca(html: str, pagina: str = IUYMCA) -> list[CarreraDeLaGuia]:
    carreras = []
    for enlace in _menu(html, "carreras"):
        carrera = _carrera(_titulo_si_mayusculas(_texto(enlace)), "", enlace["href"])
        if carrera:
            carreras.append(carrera)
    return carreras


def leer_usba(html: str, pagina: str = USBA) -> list[CarreraDeLaGuia]:
    # Under the "Licenciaturas" menu the careers go by their field alone.
    carreras = []
    for enlace in _menu(html, "licenciaturas"):
        nombre = _texto(enlace)
        if "inscripci" in enlace["href"] or "información" in nombre.lower():
            continue
        nombre = nombre if nombre.lower().startswith("licenciatura") else f"Licenciatura en {nombre}"
        carrera = _carrera(nombre, "", enlace["href"], None, None, "Grado")
        if carrera:
            carreras.append(carrera)
    return carreras


def leer_ude(html: str, pagina: str = UDE) -> list[CarreraDeLaGuia]:
    carreras, vistas = [], set()
    for bloque in _soup(html).select("li.dropdown"):
        unidad = _texto(bloque.select_one("span.nombre-completo-facultad"))
        if not unidad:
            continue
        for enlace in bloque.select("ul.dropdown-facultades a[href]"):
            nombre = _texto(enlace)
            if re.search(r"(?i)especializaci|maestr|doctorado|diplomatura", nombre) or enlace["href"] in vistas:
                continue
            vistas.add(enlace["href"])
            carrera = _carrera(nombre, unidad, enlace["href"])
            if carrera:
                carreras.append(carrera)
    return carreras


# --- Universidad Católica de Salta ------------------------------------------------------------
# A flip-box per career; its categories say the level and the way it is taught.

UCASAL_GRADO = "https://www.ucasal.edu.ar/menu-oferta-educativa-por-nivel/grado"
UCASAL_PREGRADO = "https://www.ucasal.edu.ar/menu-oferta-educativa-por-nivel/pregrado"


def leer_ucasal(html: str, pagina: str) -> list[CarreraDeLaGuia]:
    carreras, vistas = [], set()
    for item in _soup(html).select("div.e-loop-item"):
        clases = " ".join(item.get("class") or [])
        titulo = item.select_one("h3.elementor-flip-box__layer__title")
        enlace = next((a for a in item.find_all("a", href=True) if "/carrera/" in a["href"]), None)
        if not titulo or not enlace or "ciclo" in clases:
            continue
        nombre = _texto(titulo)
        if nombre.lower() in vistas:
            continue
        vistas.add(nombre.lower())
        carrera = _carrera(nombre, "", enlace["href"], None, None,
                           "Pregrado" if "pregrado" in pagina else "Grado")
        if carrera:
            carreras.append(carrera)
    return carreras


# --- Universidad Nacional de Misiones --------------------------------------------------------
# "Carreras por Facultades": each faculty's heading, then per level an accordion,
# each career with "DURACIÓN: 5 años", "Lugar de dictado: Oberá" and its link.

UNAM = "https://www.unam.edu.ar/index.php/ingresantes/carreras"


def leer_unam(html: str, pagina: str = UNAM) -> list[CarreraDeLaGuia]:
    carreras, unidad, nivel_dicho = [], "", None
    for elemento in _soup(html).find_all(["h2", "h5", "div"]):
        if elemento.name == "h2":
            texto = _texto(elemento)
            if texto.lower().startswith(("facultad", "escuela", "instituto")):
                unidad = texto
            continue
        if elemento.name == "h5":
            texto = _texto(elemento).lower()
            nivel_dicho = "Pregrado" if "pregrado" in texto else "Grado" if "carreras de grado" in texto else None
            continue
        if "el-item" not in (elemento.get("class") or []) or not nivel_dicho or not unidad:
            continue
        titulo = elemento.select_one("a.el-title")
        contenido = _texto(elemento.select_one(".uk-accordion-content"))
        enlace = elemento.select_one(".uk-accordion-content a[href]")
        lugar = re.search(r"(?i)Lugar de dictado:\s*([^.]+?)(?:\s+Más|$)", contenido)
        sedes = [clean_text(s) for s in re.split(r"\s+y\s+|,\s*|\s+-\s+", lugar.group(1))] if lugar else [None]
        for sede in sedes:
            carrera = _carrera(con_tildes(_texto(titulo)), unidad, enlace["href"] if enlace else pagina,
                               sede or None, anios(contenido), nivel_dicho)
            if carrera:
                carreras.append(carrera)
    return carreras


# --- Universidad Nacional de Catamarca ----------------------------------------------------------
# The list is data in the page: bloquesAcademicos = [{id: level, fac: faculty,
# carreras: [{n: name, d: duration, sede, u: page}]}].

UNCA = "https://www.unca.edu.ar/carreras"


def leer_unca(html: str, pagina: str = UNCA) -> list[CarreraDeLaGuia]:
    carreras = []
    for bloque in re.finditer(r"\{\s*id:\s*\"(\w+)\",\s*fac:\s*\"([^\"]+)\",\s*carreras:\s*\[(.*?)\]\s*\}", html or "", re.S):
        nivel_dicho, unidad = bloque.group(1), re.sub(r"^Fac\.\s*", "Facultad ", bloque.group(2))
        if nivel_dicho not in ("Pregrado", "Grado"):
            continue
        for item in re.finditer(r"\{\s*n:\s*'([^']+)',\s*d:\s*'([^']*)',.*?sede:\s*'([^']*)'.*?u:\s*'([^']*)'", bloque.group(3), re.S):
            nombre, duracion, sede, url = item.groups()
            for lugar in [clean_text(s) for s in sede.split("-") if clean_text(s)] or [None]:
                carrera = _carrera(nombre, unidad, url or pagina, lugar, anios(duracion), nivel_dicho)
                if carrera:
                    carreras.append(carrera)
    return carreras


# --- Universidad Católica de La Plata ------------------------------------------------------------
# A box per faculty: its name, then headings ("Carreras de Grado", "Ciclos de
# Licenciatura", "Tecnicaturas"...) each with its list of careers.

UCALP = "https://www.ucalp.edu.ar/carrera/"


def leer_ucalp(html: str, pagina: str = UCALP) -> list[CarreraDeLaGuia]:
    carreras = []
    for caja in _soup(html).select("div.carreras-box"):
        nombre_facultad = _texto(caja.find("h2"))
        if not nombre_facultad or nombre_facultad.lower() == "rectorado":
            continue
        unidad = f"Facultad de {nombre_facultad}"
        for encabezado in caja.find_all("h6"):
            texto = _texto(encabezado).lower()
            if "ciclo" in texto or "posgrado" in texto:
                continue
            nivel_dicho = "Pregrado" if re.search(r"pregrado|tecnicatura", texto) else "Grado"
            lista = encabezado.find_next_sibling("ul")
            for enlace in (lista.find_all("a", href=True) if lista else []):
                carrera = _carrera(_texto(enlace), unidad, enlace["href"], None, None, nivel_dicho)
                if carrera:
                    carreras.append(carrera)
    return carreras


# --- Universidad Nacional del Nordeste --------------------------------------------------------------
# Each faculty's heading, then each career's heading followed by its data:
# "Tipo de Título: Grado", "Duración: 6 años" and a link to its page.

UNNE = "https://www.unne.edu.ar/estudiar/facultades/ofertas-academicas-de-grado/"


def leer_unne(html: str, pagina: str = UNNE) -> list[CarreraDeLaGuia]:
    carreras, unidad = [], ""
    for encabezado in _soup(html).select("h5.elementor-heading-title"):
        texto = _texto(encabezado)
        if re.match(r"(?i)^(facultad|instituto|escuela)\b", texto):
            unidad = texto
            continue
        lista = encabezado.find_next("ul", class_="elementor-icon-list-items")
        datos = _texto(lista)
        if not unidad or "Tipo de Título" not in datos:
            continue
        tipo = re.search(r"Tipo de Título:\s*(\w+)", datos)
        enlace = lista.find("a", href=True)
        if tipo and tipo.group(1).lower() not in ("grado", "pregrado"):
            continue
        carrera = _carrera(texto, unidad, enlace["href"] if enlace else pagina, None, anios(datos),
                           "Pregrado" if tipo and tipo.group(1).lower() == "pregrado" else "Grado")
        if carrera:
            carreras.append(carrera)
    return carreras


# --- Universidad de la Defensa Nacional -------------------------------------------------------------
# A page per faculty, headings PREGRADO / GRADO / POSGRADO, each career an
# accordion item. "(Formación militar)" says it is the officers' training, open
# only to those who enter a force's academy; it is a career all the same.

UNDEF = tuple("https://undef.edu.ar/oferta-academica/" + s + "/" for s in (
    "oferta-academica-facultad-del-ejercito", "oferta-academica-facultad-dela-armada",
    "oferta-academica-facultad-dela-fuerza-aerea", "oferta-academica-facultad-militar-conjunta",
    "oferta-academica-fadena", "oferta-academica-facultad-de-ingenieria-del-ejercito",
    "oferta-academica-facultad-de-ingenieria-del-cruc-iua",
    "oferta-academica-facultad-de-ciencias-dela-administracion-cruc-iua", "oferta-academica-rectorado"))


def leer_undef(html: str, pagina: str) -> list[CarreraDeLaGuia]:
    soup = _soup(html)
    carreras, nivel_dicho, unidad = [], None, ""
    for elemento in soup.find_all(["h2", "div"]):
        if elemento.name == "h2":
            texto = _texto(elemento)
            if texto.upper() in ("PREGRADO", "GRADO", "POSGRADO"):
                nivel_dicho = texto.title() if texto.upper() != "POSGRADO" else None
            elif texto.lower().startswith(("facultad", "rectorado")):
                unidad = con_tildes(texto) if texto.isupper() else texto
            continue
        if "e-n-accordion-item-title-text" not in (elemento.get("class") or []) or not nivel_dicho:
            continue
        nombre = clean_text(re.sub(r"\((?:formaci[oó]n militar|militar)\)", "", _texto(elemento), flags=re.I))
        carrera = _carrera(nombre, unidad if unidad.lower().startswith("facultad") else "", pagina, None, None,
                           nivel_dicho)
        if carrera:
            carreras.append(carrera)
    return carreras


# --- Universidad Nacional de Jujuy ------------------------------------------------------------------
# Each faculty's careers come from its public service (apis/consulta_carrera.php?
# unidad=N), by campus and building; a career listed once per title it gives
# (its intermediate one too) is one career.

UNJU = tuple(f"https://unju.edu.ar/apis/consulta_carrera.php?unidad={n}" for n in (1, 2, 3, 4, 6, 7))


def leer_unju(html: str, pagina: str) -> list[CarreraDeLaGuia]:
    try:
        datos = json.loads(html or "{}")
    except ValueError:
        return []
    carreras, vistas = [], set()
    unidad_pedida = re.search(r"unidad=(\d+)", pagina).group(1)
    for unidad in datos.get("unidades") or []:
        if str(unidad.get("id")) != unidad_pedida:
            continue
        for sede in unidad.get("sedes") or []:
            for edificio in sede.get("edificios") or []:
                for item in edificio.get("carreras") or []:
                    clave = (item.get("nombre"), sede.get("nombre"))
                    if clave in vistas:
                        continue
                    vistas.add(clave)
                    carrera = _carrera(item.get("nombre") or "", clean_text(unidad.get("nombre") or ""),
                                       item.get("link") or pagina, clean_text(sede.get("nombre") or "") or None,
                                       anios((item.get("duracion") or "").replace("1/2", "y medio").replace(" y medio años", " años y medio")))
                    if carrera:
                        carreras.append(carrera)
    return carreras


# --- Universidad Nacional de La Pampa ------------------------------------------------------------------
# A grid: each career's item has its faculty and level as classes
# ("feco grado", "fagro inter" for pregrado).

UNLPAM = "https://www.unlpam.edu.ar/ingresantes?showall=&start=1"
_FACULTADES_UNLPAM = {
    "fagro": "Facultad de Agronomía", "fsalud": "Facultad de Ciencias de la Salud",
    "feco": "Facultad de Ciencias Económicas y Jurídicas", "fhuma": "Facultad de Ciencias Humanas",
    "finge": "Facultad de Ingeniería", "fnatu": "Facultad de Ciencias Exactas y Naturales",
    "fvete": "Facultad de Ciencias Veterinarias",
}


def leer_unlpam(html: str, pagina: str = UNLPAM) -> list[CarreraDeLaGuia]:
    carreras = []
    for item in _soup(html).select("ul.day-grid > li"):
        clases = item.get("class") or []
        nivel_dicho = "Grado" if "grado" in clases else "Pregrado" if "inter" in clases else None
        enlace = item.find("a", href=True)
        titulo = item.find("h3")
        if not nivel_dicho or not enlace or not titulo:
            continue
        pequenio = titulo.find("small")
        if pequenio:
            pequenio.decompose()
        unidad = next((_FACULTADES_UNLPAM[c] for c in clases if c in _FACULTADES_UNLPAM), "")
        carrera = _carrera(_texto(titulo), unidad, enlace["href"], None, None, nivel_dicho)
        if carrera:
            carreras.append(carrera)
    return carreras


# --- Universidad Nacional de Salta ------------------------------------------------------------------------
# An accordion per career under the level's heading; its content lists the
# faculty, the duration ("2 1/2 años de duración"), the towns and the plan.

UNSA = "https://www.unsa.edu.ar/carreras/"


def leer_unsa(html: str, pagina: str = UNSA) -> list[CarreraDeLaGuia]:
    carreras, nivel_dicho = [], None
    for elemento in _soup(html).find_all(["h2", "h3", "span", "div"]):
        clases = elemento.get("class") or []
        if elemento.name in ("h2", "h3"):
            texto = _texto(elemento).lower()
            if texto in ("pregrado", "grado", "posgrado", "carreras de pregrado", "carreras de grado", "carreras de posgrado"):
                nivel_dicho = None if "posgrado" in texto else ("Pregrado" if "pregrado" in texto else "Grado")
            continue
        if "eael-accordion-tab-title" not in clases or not nivel_dicho:
            continue
        cabecera = elemento.find_parent("div", class_="eael-accordion-header")
        contenido = cabecera.find_next_sibling("div") if cabecera else None
        items = [_texto(li) for li in (contenido.find_all("li") if contenido else [])]
        unidad = next((re.sub(r"\bCs\.\s*", "Ciencias ", i).replace("Exáctas", "Exactas") for i in items
                       if i.lower().startswith(("facultad", "escuela", "sede"))), "")
        duracion = next((i for i in items if "año" in i.lower()), "")
        lugares = next((i for i in items if i not in (unidad, duracion) and not i.lower().startswith(("plan", "facultad"))
                        and re.search(r"[A-ZÁÉÍÓÚ]", i)), "")
        enlace = contenido.find("a", href=True) if contenido else None
        duracion = duracion.replace("1/2", "y medio")
        for sede in [clean_text(s) for s in re.split(r"\s*[–-]\s*|,\s*", lugares) if clean_text(s)] or [None]:
            carrera = _carrera(_texto(elemento), unidad if unidad.lower().startswith("facultad") else "",
                               enlace["href"] if enlace else pagina, sede,
                               anios(re.sub(r"(\d)\s+y medio años", r"\1 años y medio", duracion)), nivel_dicho)
            if carrera:
                carreras.append(carrera)
    return carreras


# --- Universidad San Pablo - Tucumán ------------------------------------------------------------------------
# Its public service lists every career with its campus and modality.

USPT = "https://api.uspt.edu.ar/public/carreras"


def leer_uspt(html: str, pagina: str = USPT) -> list[CarreraDeLaGuia]:
    try:
        datos = json.loads(html or "{}").get("data") or []
    except ValueError:
        return []
    carreras = []
    for item in datos:
        nombre = item.get("name") or ""
        sede = clean_text(item.get("sede") or "")
        carrera = _carrera(nombre, "", "https://www.uspt.edu.ar/carreras", f"Sede {sede.title()}" if sede else None)
        if carrera:
            carreras.append(carrera)
    return carreras


# --- Universidad de Concepción del Uruguay -------------------------------------------------------------------
# Every career in the page as a portfolio item, its level, towns and faculty
# as categories.

UCU = "https://ucu.edu.ar/carreras/"
_SEDES_UCU = {"concepcion-del-uruguay": "Concepción del Uruguay", "gualeguaychu": "Gualeguaychú",
              "rosario": "Rosario", "santa-fe": "Santa Fe", "colon": "Colón", "parana": "Paraná"}


def leer_ucu(html: str, pagina: str = UCU) -> list[CarreraDeLaGuia]:
    carreras = []
    for item in _soup(html).select("div.et_pb_portfolio_item"):
        clases = " ".join(item.get("class") or [])
        nivel_dicho = "Pregrado" if "project_category_pregrado" in clases else \
            "Grado" if "project_category_grado" in clases else None
        enlace = item.select_one("h2 a[href]")
        if not nivel_dicho or not enlace:
            continue
        sedes = [nombre for slug, nombre in _SEDES_UCU.items() if f"project_category_{slug} " in clases + " "]
        for sede in sedes or [None]:
            carrera = _carrera(_texto(enlace), "", enlace["href"], sede, None, nivel_dicho)
            if carrera:
                carreras.append(carrera)
    return carreras


# --- Universidad Nacional de Villa María ----------------------------------------------------------------------
# A toggle per institute; inside, "Pregrado ///" and "Grado ///" and the
# careers' links, a campus other than Villa María in parentheses after one.

UNVM = "https://www.unvm.edu.ar/unidades-academicas/"


def leer_unvm(html: str, pagina: str = UNVM) -> list[CarreraDeLaGuia]:
    carreras = []
    for toggle in _soup(html).select("div.et_pb_toggle"):
        titulo = _texto(toggle.select_one("h5.et_pb_toggle_title"))
        contenido = toggle.select_one("div.et_pb_toggle_content")
        if not titulo or not contenido:
            continue
        unidad = con_tildes(titulo) if titulo.isupper() else titulo
        nivel_dicho = None
        for elemento in contenido.find_all(["h4", "a"]):
            if elemento.name == "h4":
                texto = _texto(elemento).lower()
                nivel_dicho = None if "posgrado" in texto else "Pregrado" if "pregrado" in texto else \
                    "Grado" if "grado" in texto else None
                continue
            if not nivel_dicho or not elemento.get("href"):
                continue
            despues = elemento.next_sibling
            sede = re.search(r"\(Sede ([^)]+)\)", str(despues or ""))
            carrera = _carrera(_texto(elemento), unidad, elemento["href"],
                               clean_text(sede.group(1)) if sede else "Villa María", None, nivel_dicho)
            if carrera:
                carreras.append(carrera)
    return carreras


# --- Universidad de Congreso ---------------------------------------------------------------------------------
# The "Nuestras carreras" menu: each faculty's link, its careers under it.

UCONGRESO = "https://www.ucongreso.edu.ar/"


def leer_ucongreso(html: str, pagina: str = UCONGRESO) -> list[CarreraDeLaGuia]:
    carreras, vistas = [], set()
    for enlace in _soup(html).select("a[href*='/facultad/']"):
        unidad = _texto(enlace)
        lista = enlace.find_next_sibling("ul")
        if not unidad.lower().startswith("facultad") or not lista:
            continue
        for hijo in lista.select("a[href*='/carrera/']"):
            if hijo["href"] in vistas:
                continue
            vistas.add(hijo["href"])
            carrera = _carrera(_texto(hijo), unidad, hijo["href"])
            if carrera:
                carreras.append(carrera)
    return carreras


# --- Universidad Nacional de la Patagonia Austral -----------------------------------------------------------
# Every career's name in the page's lists, "- Título Intermedio ..." after some.

UNPA = "https://propuestaacademica.unpa.edu.ar/vista/index.php"


def leer_unpa(html: str, pagina: str = UNPA) -> list[CarreraDeLaGuia]:
    carreras, vistas = [], set()
    for enlace in _soup(html).select("a.modal-trigger[id]"):
        nombre = clean_text(re.split(r"\s+-\s+T[ií]tulo Intermedio", _texto(enlace))[0])
        if nombre.lower() in vistas:
            continue
        vistas.add(nombre.lower())
        carrera = _carrera(nombre, "", pagina)
        if carrera:
            carreras.append(carrera)
    return carreras
