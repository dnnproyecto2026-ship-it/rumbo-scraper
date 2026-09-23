"""Reading what a university publishes about itself rather than about a career.

Three sections that no career page fills and that every university does
publish, each on a page of its own: where it teaches, the academic units it
teaches through, and the people who run them.

They are read here for every university at once, the same way the footer is,
because a university has one page of campuses and one of authorities however
many careers it offers.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from rumbo_scraper.normalizers.text import clean_text, comparison_key
from rumbo_scraper.parsers.generico import _lineas, _quitar_accesorios, _soup

# What a university calls the page that lists each of these.
PAGINAS: tuple[tuple[str, str], ...] = (
    ("sedes", r"sedes?|c[óo]mo llegar|d[óo]nde estamos|nuestras sedes|"
              r"campus|localizaci[óo]n|ubicaci[óo]n|contacto"),
    ("facultades", r"facultades|unidades acad[ée]micas|escuelas|"
                   r"departamentos|institutos|nuestra oferta"),
    ("autoridades", r"autoridades|rectorado|consejo superior|gobierno|"
                    r"equipo de gesti[óo]n|conducci[óo]n"),
)


def descubrir(html: str, pagina: str, dominio: str) -> dict[str, list[str]]:
    """The pages a site links for each of the three sections."""
    encontrado: dict[str, list[str]] = {clave: [] for clave, _ in PAGINAS}
    for anchor in _soup(html).find_all("a", href=True):
        etiqueta = clean_text(anchor.get_text(" ", strip=True))
        if not etiqueta or len(etiqueta) > 40:
            continue
        url = urljoin(pagina, clean_text(anchor["href"])).split("#")[0]
        host = (urlparse(url).netloc or "").lower().removeprefix("www.")
        if not host.endswith(dominio):
            continue
        for clave, patron in PAGINAS:
            if re.search(rf"\b(?:{patron})\b", comparison_key(etiqueta), re.I):
                if url not in encontrado[clave]:
                    encontrado[clave].append(url)
                break
    return {clave: urls[:3] for clave, urls in encontrado.items()}


# ------------------------------------------------------------------- campuses

# An Argentine address: a street and its number. The number is what tells an
# address from the name of a neighbourhood, and the word before it has to
# read like a street rather than like a year or a telephone.
_UNA_DIRECCION = re.compile(
    r"^(?P<calle>(?:Av\.?|Avda\.?|Avenida|Calle|Ruta|Bv\.?|Boulevard|Diag\.?|"
    r"Diagonal|Pasaje|Pje\.?)?\s*[A-ZÁÉÍÓÚÑ][\w.'’-]*(?:\s+(?:de|del|la|los|"
    r"las|y)?\s*[\w.'’-]+){0,4}?)\s+(?:n[°ºo]\.?\s*)?(?P<numero>\d{1,5})"
    r"(?:\s*[,.–-]|\s|$)")
# What carries a number and is not an address.
_NO_ES_DIRECCION = re.compile(
    r"(?i)\b(tel|te|fax|cp|c\.p|whatsapp|int|interno|piso|aula|res(?:oluci[óo]n)?|"
    r"expediente|a[ñn]o|hs?\b|horario|\d{4}\s*-\s*\d{4})\b|@|https?:|\|"
    # A year is not a street number, and a line that ends in one is a date.
    r"|\b(?:19|20)\d{2}\s*$")
# The word a sentence opens with. An address opens with a street.
_ARRANCA_UNA_FRASE = frozenset(
    "el la los las un una este esta nuestro nuestra su sus con para por "
    "desde hasta entre cuenta tiene ofrece son fue es al del de y o".split())
# A street the university names without a type word in front of it is only
# read when the line is short enough to be an address and nothing else.
MAX_PALABRAS_DIRECCION = 7
# The word a university uses over the address of one of its campuses.
_UNA_SEDE = re.compile(
    r"(?i)^(sede|subsede|campus|anexo|edificio|facultad|escuela|delegaci[óo]n|"
    r"centro regional|predio|complejo)\b")


# An address with the kind of way spelled out can sit anywhere in a line: in
# a footer it follows the name of the university and precedes the postcode,
# "Universidad Nacional de La Plata Av. 7 N° 776, La Plata (CP 1900)". The
# kind of way is what makes it safe to find it mid-line, so only the forms a
# sentence does not use are taken: "Av." with its full stop, never "av".
_DIRECCION_CON_TIPO = re.compile(
    r"(?P<calle>(?:Av\.|Avda\.|Avenida|Calle|Bv\.|Boulevard|Diag\.|Diagonal|"
    r"Pasaje|Pje\.)\s+[\w.'’]+(?:\s+[\w.'’]+){0,4}?)"
    r"\s+(?:N[°º]\.?\s*)?(?:(?P<numero>\d{1,5})\b(?![-\d]|\s*(?:hs|km|%))"
    # "Av. Haya de la Torre s/n": a street with no number is how a campus
    # built on its own grounds is addressed, and the number stays empty.
    r"|(?P<sin_numero>s/n)\b)", re.I)
# A street may be named after a year, and a number may look like one: an
# address is told from a date by the town that follows it,
# "Florencio Varela 1903, San Justo".
_SIGUE_UNA_LOCALIDAD = re.compile(r"\d{4},\s*[A-ZÁÉÍÓÚÑ][a-záéíóúñ]")
_MESES = frozenset("enero febrero marzo abril mayo junio julio agosto septiembre "
                   "setiembre octubre noviembre diciembre".split())


def sin_nombre(calle: str, numero: str | None = None) -> str:
    """The name of an address the page gives no name to.

    It used to be "Sede central", which states something no page said: UCA's
    campus in Rosario was stored as its main one. It was also one name for
    every unnamed address of a university, and campuses are stored one per
    name, so the second overwrote the first. The street is neither a claim
    nor shared.
    """
    return f"Sede {calle} {numero}" if numero else f"Sede {calle}"


# The first word of a line with a number in it that no street starts with.
_NO_ABRE_UNA_CALLE = frozenset(
    "error alumnos alumno aulas aula experiencias mayores menores hasta "
    "capacidad cupos cupo mas".split())
_PREPOSICIONES = frozenset("de del para con a al en por".split())


def _es_calle(calle: str, numero: str | None) -> bool:
    """Whether a street and number read like an address at all."""
    palabras = comparison_key(calle).split()
    if not palabras or palabras[0] in _NO_ABRE_UNA_CALLE:
        return False
    # "Aulas con capacidad para 40", "Mayores de 25": a count, not a street.
    if palabras[-1] in _PREPOSICIONES:
        return False
    # "Alumnos 0800": the start of a free telephone line.
    if numero and numero.startswith("0"):
        return False
    return True


def leer_sedes(html: str, pagina: str) -> list[dict[str, Any]]:
    """Read the campuses a page lists, with the address of each.

    A campus is a name and an address underneath it. Where the page gives an
    address without naming the campus, the address is kept under the name the
    university gave the page, because an address with no name still says
    where the university teaches.
    """
    soup = _soup(html)
    for element in soup(["script", "style", "noscript", "form", "select"]):
        element.decompose()
    _quitar_accesorios(soup)

    sedes: list[dict[str, Any]] = []
    vistas: set[str] = set()
    nombre: str | None = None
    lineas_desde_el_nombre = 0
    for linea in _lineas(soup):
        if not linea or len(linea) > 120:
            continue
        if _UNA_SEDE.match(linea) and len(linea) <= 70 \
                and "virtual" not in comparison_key(linea):
            nombre = clean_text(linea).strip(" :.-")
            lineas_desde_el_nombre = 0
            continue
        lineas_desde_el_nombre += 1
        # A name belongs to the address right under it. One a dozen lines up
        # is a menu entry: "Escuela de Artes..." over UNLaM's footer.
        if lineas_desde_el_nombre > 3:
            nombre = None
        con_tipo_en_linea = _DIRECCION_CON_TIPO.search(linea)
        if con_tipo_en_linea and not re.search(r"@|https?:", linea):
            calle = clean_text(con_tipo_en_linea.group("calle")).strip(" ,.-")
            numero = con_tipo_en_linea.group("numero")
            # "Pabellón Argentina, Av. Haya de la Torre s/n": what precedes
            # the street on its own line is the building's name.
            antes = clean_text(linea[:con_tipo_en_linea.start()]).strip(" ,.-:")
            propio = antes if 3 <= len(antes) <= 50 and "universidad" not in \
                comparison_key(antes) else None
            clave = comparison_key(f"{calle} {numero or ''}")
            if clave not in vistas and _es_calle(calle, numero):
                vistas.add(clave)
                sedes.append({"nombre_sede": nombre or propio or sin_nombre(calle, numero),
                              "calle": calle, "numero": numero, "fuente": pagina})
                nombre = None
            continue
        if _NO_ES_DIRECCION.search(linea) and not _SIGUE_UNA_LOCALIDAD.search(linea):
            continue
        if comparison_key(linea).split()[0] in _ARRANCA_UNA_FRASE:
            continue
        match = _UNA_DIRECCION.match(linea)
        if not match:
            continue
        calle = clean_text(match.group("calle")).strip(" ,.-")
        numero = match.group("numero")
        if len(calle) < 4 or comparison_key(calle) in _NO_ES_CALLE \
                or not _es_calle(calle, numero):
            continue
        # Either the university named the kind of way, or the line is short
        # enough that it can only be an address.
        con_tipo = re.match(r"(?i)^(av|avda|avenida|calle|ruta|bv|boulevard|"
                            r"diag|diagonal|pasaje|pje|camino|autopista)\b", calle)
        if not con_tipo:
            if len(linea.split()) > MAX_PALABRAS_DIRECCION:
                continue
            # Without a word naming the kind of way, the street has to read
            # like a name and the number like a number: a line in capitals is
            # a banner and a four-digit year is a date.
            if calle.isupper():
                continue
            if 1900 <= int(numero) <= 2099 and (
                    not _SIGUE_UNA_LOCALIDAD.search(linea)
                    or _MESES & set(comparison_key(calle).split())):
                continue
        clave = comparison_key(f"{calle} {numero}")
        if clave in vistas:
            continue
        vistas.add(clave)
        sedes.append({"nombre_sede": nombre or sin_nombre(calle, numero),
                      "calle": calle, "numero": numero, "fuente": pagina})
        nombre = None
    return sedes


# A word a university prints with a number beside it that is never a street.
_NO_ES_CALLE = frozenset({
    "tel", "telefono", "fax", "whatsapp", "codigo postal", "buenos aires",
    "argentina", "lunes a viernes", "horario de atencion", "tour",
    "tour virtual", "aula", "sala", "box", "oficina", "local", "plan",
    "beca", "becas", "cupo", "programa", "resolucion", "expediente",
    "campus virtual", "nivel", "modulo", "grupo", "turno",
})

_TIPOS_SEDE = ((r"campus|predio|complejo|ciudad universitaria", "Campus"),
               (r"anexo|subsede|delegaci[óo]n", "Anexo"))


def tipo_de_sede(nombre: str) -> str:
    """The kind of campus the schema files a name under."""
    clave = comparison_key(nombre)
    for patron, tipo in _TIPOS_SEDE:
        if re.search(patron, clave):
            return tipo
    return "Otro"


# ------------------------------------------------------------ academic units

# A "Centro de ..." and an "Instituto de ..." at a university are nearly
# always research, not teaching: UBA publishes some twenty institutes and not
# one of them offers a degree. The teaching units of the country are the
# facultad, the escuela and the departamento. A university that does call its
# teaching units institutes still names them on the page of each career,
# under the label "Unidad Académica", which is where the career reader takes
# them from.
_UNA_UNIDAD = re.compile(
    r"(?i)^(facultad|escuela|departamento)\s+"
    r"(?:de|del|en|para)\s+[\wÁÉÍÓÚÑáéíóúñ]")
# A unit the schema has no kind for, or one that is not academic.
_NO_ES_UNIDAD_ACADEMICA = re.compile(
    r"(?i)^(instituto de investigaci|escuela secundaria|escuela primaria|"
    r"escuela de educaci[óo]n (?:media|secundaria)|escuela de posgrado|"
    r"instituto de idiomas|escuela de oficios|"
    r"escuela de (?:verano|invierno|primavera|otoño|otono)|"
    # An office of the administration is named the same way and teaches
    # nobody: "Departamento de Alumnos", "Departamento de Compras".
    r"departamento de (?:alumnos|personal|compras|sistemas|mantenimiento|"
    r"recursos humanos|contabilidad|tesorer[íi]a|legales|prensa|"
    r"despacho|mesa de entradas|suministros|servicios generales|"
    r"concursos|posgrado|extensi[óo]n|investigaci[óo]n|bienestar))")

_TIPOS_UNIDAD = (("facultad", "Facultad"), ("escuela", "Escuela"),
                 ("departamento", "Departamento"), ("instituto", "Departamento"),
                 ("centro", "Centro"), ("colegio", "Escuela"))


def leer_facultades(html: str, pagina: str) -> list[dict[str, str]]:
    """Read the academic units a page lists.

    A unit is named in full -- "Facultad de Ciencias Económicas" -- wherever a
    university lists them, in a link, a heading or a line of its own. The full
    name is what makes it readable: "Económicas" alone is how the menu of that
    faculty's own site writes it, and that is a different page.
    """
    soup = _soup(html)
    for element in soup(["script", "style", "noscript", "form", "select"]):
        element.decompose()

    unidades: list[dict[str, str]] = []
    vistas: set[str] = set()
    textos = [clean_text(anchor.get_text(" ", strip=True))
              for anchor in soup.find_all("a")]
    textos += [clean_text(h.get_text(" ", strip=True))
               for h in soup.find_all(["h2", "h3", "h4", "li"])]
    textos += _lineas(soup)
    for texto in textos:
        if not (12 <= len(texto) <= 90) or len(texto.split()) > 10:
            continue
        if not _UNA_UNIDAD.match(texto) or _NO_ES_UNIDAD_ACADEMICA.match(texto):
            continue
        clave = comparison_key(texto)
        if clave in vistas:
            continue
        vistas.add(clave)
        unidades.append({"nombre_facultad": clean_text(texto),
                         "tipo_unidad": tipo_de_unidad(texto), "fuente": pagina})
    return unidades


_UNIDAD_EN_LA_RUTA = {"departamentos": "Departamento", "facultades": "Facultad",
                      "escuelas": "Escuela"}
_UNIDAD_EN_EL_SLUG = re.compile(
    r"^(?P<tipo>facultad|escuela-superior|escuela|departamento)-(?:de|del)-(?P<resto>.+)$")
_TIPO_EN_EL_SLUG = {"facultad": "Facultad", "escuela-superior": "Escuela Superior",
                    "escuela": "Escuela", "departamento": "Departamento"}


def unidades_por_enlace(html: str, pagina: str) -> list[dict[str, str]]:
    """Read the units a menu names by their subject alone.

    UNLa lists "Humanidades y Artes" under /departamentos/, and Morón links
    "Ciencias de la Salud" to .../escuela-superior-de-ciencias-de-la-salud.
    The full name is what the address says the link is: the folder names the
    kind of unit, or the address spells the whole name and the label is its
    subject word for word. Anything short of that is left unread.
    """
    from urllib.parse import unquote, urljoin, urlparse
    unidades: list[dict[str, str]] = []
    vistas: set[str] = set()
    for anchor in _soup(html).find_all("a", href=True):
        etiqueta = clean_text(anchor.get_text(" ", strip=True))
        if not etiqueta or not (4 <= len(etiqueta) <= 60) or _UNA_UNIDAD.match(etiqueta):
            continue
        partes = [p for p in unquote(urlparse(urljoin(pagina, anchor["href"])).path)
                  .lower().split("/") if p]
        if not partes:
            continue
        nombre = None
        if len(partes) >= 2 and partes[-2] in _UNIDAD_EN_LA_RUTA:
            if comparison_key(etiqueta).replace(" ", "-") == comparison_key(partes[-1]) \
                    or comparison_key(partes[-1]).startswith(
                        comparison_key(etiqueta).split()[0]):
                nombre = f"{_UNIDAD_EN_LA_RUTA[partes[-2]]} de {etiqueta}"
        else:
            slug = _UNIDAD_EN_EL_SLUG.match(comparison_key(partes[-1]))
            if slug and slug.group("resto") == comparison_key(etiqueta).replace(" ", "-"):
                nombre = f"{_TIPO_EN_EL_SLUG[slug.group('tipo')]} de {etiqueta}"
        if not nombre or _NO_ES_UNIDAD_ACADEMICA.match(nombre):
            continue
        clave = comparison_key(nombre)
        if clave in vistas:
            continue
        vistas.add(clave)
        unidades.append({"nombre_facultad": nombre, "tipo_unidad": tipo_de_unidad(nombre),
                         "fuente": pagina})
    return unidades


def tipo_de_unidad(nombre: str) -> str:
    clave = comparison_key(nombre)
    for token, tipo in _TIPOS_UNIDAD:
        if clave.startswith(token):
            return tipo
    return "Departamento"


# ---------------------------------------------------------------- the people

def leer_autoridades(html: str, pagina: str) -> list[dict[str, str]]:
    """Read the people a page of authorities names, with the post each holds.

    The page of authorities writes a post and a name together, in either
    order and separated in whatever way the site prefers: on one line with a
    dash, or on two lines with the post over the name. Both are read, and a
    line only becomes a person when one half reads as a post and the other as
    a name.
    """
    from rumbo_scraper.parsers.generico import cargo_de, leer_autoridades as por_guion

    personas: list[dict[str, str]] = []
    vistas: set[str] = set()

    def guardar(nombre: str, cargo: str, unidad: str | None = None) -> None:
        nombre = _sin_tratamiento(nombre)
        tipo = cargo_de(cargo)
        if not tipo or not _UN_NOMBRE_PROPIO.match(nombre) or cargo_de(nombre):
            return
        clave = comparison_key(f"{nombre}|{cargo}")
        if clave in vistas:
            return
        vistas.add(clave)
        persona = {"nombre": nombre, "cargo": clean_text(cargo), "tipo": tipo}
        # Only a post a faculty has is filed under the heading above it: a
        # rector listed below a menu of faculties runs none of them.
        if unidad and _CARGO_DE_UNA_UNIDAD.search(comparison_key(cargo)):
            persona["unidad"] = unidad
        personas.append(persona)

    for persona in por_guion(html):
        guardar(persona["nombre"], persona["cargo"])
    por_guion_leidas = len(personas)

    soup = _soup(html)
    for element in soup(["script", "style", "noscript", "nav", "footer", "header"]):
        element.decompose()
    _quitar_accesorios(soup)
    lineas = [linea for linea in _lineas(soup) if linea]
    # The name and the post run together on one line, with nothing between
    # them: "Fernando Tauber Presidente de la UNLP". The post is found by the
    # word that opens it, and the name is what comes before.
    for linea in lineas:
        if not (12 <= len(linea) <= 90):
            continue
        match = _EMPIEZA_EL_CARGO.search(linea)
        if not match or match.start() == 0:
            continue
        guardar(clean_text(linea[:match.start()]), clean_text(linea[match.start():]))

    # The post over the name, which is how a page of authorities is laid out
    # when it is a list rather than a table. A page that lists every faculty's
    # dean puts the name of the faculty over each, a line or three above.
    # Each line is used once, from the top: in "Decano / Juan Pérez / Rector
    # / María López" Juan Pérez is the dean and not also the rector, which is
    # what pairing every line with both its neighbours made him.
    unidad: str | None = None
    desde_la_unidad = 0
    i = 0
    while i < len(lineas) - 1:
        anterior, siguiente = lineas[i], lineas[i + 1]
        desde_la_unidad += 1
        if _UNA_UNIDAD.match(anterior) and len(anterior) <= 90 \
                and not _NO_ES_UNIDAD_ACADEMICA.match(anterior):
            unidad, desde_la_unidad = clean_text(anterior), 0
            i += 1
            continue
        vigente = unidad if desde_la_unidad <= _LINEAS_BAJO_LA_UNIDAD else None
        if len(anterior) <= 70 and len(siguiente) <= 70:
            if cargo_de(anterior) and not cargo_de(siguiente) and _es_persona(siguiente):
                guardar(clean_text(siguiente), anterior, vigente)
                i += 2
                continue
            if cargo_de(siguiente) and not cargo_de(anterior) and _es_persona(anterior):
                guardar(clean_text(anterior), siguiente, vigente)
                i += 2
                continue
        i += 1
    if _se_contradice(personas[por_guion_leidas:]):
        return personas[:por_guion_leidas]
    return personas


def _es_persona(linea: str) -> bool:
    """Whether a line can be the name beside a post: a person, not a place."""
    clave = comparison_key(linea)
    return bool(_UN_NOMBRE_PROPIO.match(_sin_tratamiento(clean_text(linea)))) \
        and not _UNA_UNIDAD.match(linea) and "universidad" not in clave \
        and clave.split()[:1] != [] and clave.split()[0] not in _NO_ABRE_UN_NOMBRE


# "Sede Patagonia" reads like a first name and a surname and is a campus.
_NO_ABRE_UN_NOMBRE = frozenset(
    "sede anexo campus facultad escuela departamento instituto centro area "
    "licenciatura carrera secretaria direccion".split())


def _se_contradice(personas: list[dict[str, str]]) -> bool:
    """Whether a page read as pairs has been read out of step.

    A faculty has one dean and a person is dean of one faculty. When the
    pairs a page yields make somebody dean of two faculties, or give one
    faculty two deans, the posts and the names were paired a line out of step
    somewhere -- Austral's page made one person the dean of Communication and
    of Biomedical Sciences -- and none of its pairs can be trusted.
    """
    def es_decano(cargo: str) -> bool:
        clave = comparison_key(cargo)
        return bool(re.search(r"\bdecan[oa]\b", clave)) and "vice" not in clave

    por_persona: dict[str, set[str]] = {}
    por_unidad: dict[str, set[str]] = {}
    for persona in personas:
        if not es_decano(persona["cargo"]):
            continue
        unidad = comparison_key(persona.get("unidad") or persona["cargo"])
        nombre = comparison_key(persona["nombre"])
        por_persona.setdefault(nombre, set()).add(unidad)
        por_unidad.setdefault(unidad, set()).add(nombre)
    return any(len(v) > 1 for v in por_persona.values()) or any(
        len(v) > 1 for v in por_unidad.values())


# The posts a faculty, a school or a department has of its own.
_CARGO_DE_UNA_UNIDAD = re.compile(
    r"\b(?:vice)?decan[oa]\b|\bdirector[a]?\b|\bsecretari[oa]\b|\bcoordinador[a]?\b")
# How far under the name of a unit its authorities are still its own.
_LINEAS_BAJO_LA_UNIDAD = 4


# The degree a university prints in front of a name. It is a courtesy, not
# part of the name, and it is what makes the same person read as two.
_UN_TRATAMIENTO = re.compile(
    r"(?i)^((?:prof|dr|dra|lic|mag|mg|ing|cdor|cra|cr|arq|esp|abog|med|"
    r"psic|od|farm|bioq|tec|sr|sra|mtro|mtra)\.?\s+)+")


def _sin_tratamiento(nombre: str) -> str:
    """The name of a person without the degrees printed in front of it."""
    return clean_text(_UN_TRATAMIENTO.sub("", clean_text(nombre)))


# The word that opens a post, wherever it appears in the line.
_EMPIEZA_EL_CARGO = re.compile(
    r"(?i)\b(?:vice-?rrector[a]?|rector[a]?|presidente|"
    r"(?:vice)?decan[oa]|(?:pro)?secretari[oa]|(?:co)?director[a]?|"
    r"coordinador[a]?|administrador[a]?|jefe)\b")

# A person's name: two to five words that each open in capitals. The page of
# authorities also prints the name of the university that way, so a name that
# reads as a post is never taken for a person.
_UN_NOMBRE_PROPIO = re.compile(
    r"^(?:[A-ZÁÉÍÓÚÑÜ][\w'’.-]+(?:\s+(?:de|del|la|los|y)\s+)?\s*){2,5}$")
