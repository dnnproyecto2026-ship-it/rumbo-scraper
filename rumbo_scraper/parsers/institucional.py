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
    for linea in _lineas(soup):
        if not linea or len(linea) > 120:
            continue
        if _UNA_SEDE.match(linea) and len(linea) <= 70:
            nombre = clean_text(linea).strip(" :.-")
            continue
        if _NO_ES_DIRECCION.search(linea):
            continue
        if comparison_key(linea).split()[0] in _ARRANCA_UNA_FRASE:
            continue
        match = _UNA_DIRECCION.match(linea)
        if not match:
            continue
        calle = clean_text(match.group("calle")).strip(" ,.-")
        numero = match.group("numero")
        if len(calle) < 4 or comparison_key(calle) in _NO_ES_CALLE:
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
            if calle.isupper() or 1900 <= int(numero) <= 2099:
                continue
        clave = comparison_key(f"{calle} {numero}")
        if clave in vistas:
            continue
        vistas.add(clave)
        sedes.append({"nombre_sede": nombre or "Sede central",
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

    def guardar(nombre: str, cargo: str) -> None:
        nombre = _sin_tratamiento(nombre)
        tipo = cargo_de(cargo)
        if not tipo or not _UN_NOMBRE_PROPIO.match(nombre) or cargo_de(nombre):
            return
        clave = comparison_key(f"{nombre}|{cargo}")
        if clave in vistas:
            return
        vistas.add(clave)
        personas.append({"nombre": nombre, "cargo": clean_text(cargo), "tipo": tipo})

    for persona in por_guion(html):
        guardar(persona["nombre"], persona["cargo"])

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
    # when it is a list rather than a table.
    for anterior, siguiente in zip(lineas, lineas[1:]):
        if len(anterior) > 70 or len(siguiente) > 70:
            continue
        if cargo_de(anterior) and not cargo_de(siguiente):
            guardar(clean_text(siguiente), anterior)
        elif cargo_de(siguiente) and not cargo_de(anterior):
            guardar(clean_text(anterior), siguiente)
    return personas


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
