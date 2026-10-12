"""The photographs of a university's buildings and spaces, read from its pages.

A photograph is kept only when its own words say which space it shows: its
alt text, its title, the caption beside it or the name of its file must name
a campus, a building, a classroom, a laboratory, a library, a dining hall or a
sports ground. The page it sits on only tells the campus (sede) it belongs to,
never what it shows, because a page about the library also carries its
librarian's portrait and the covers of its books. A photograph whose words
name a person, an event, a logo or a flyer is not kept even when they also
name a space: "the rector at the opening of the new building" is a portrait.

What this module cannot tell from words alone (a photograph with a caption
printed over it, a watermark) is left to the size rule and to the person who
reviews the result.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import parse_qs, unquote, urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from rumbo_scraper.normalizers.text import clean_text

# The pages of a site that show its spaces, by the words of their link or
# address.
PAGINAS = re.compile(
    r"campus|sedes?\b|instalaciones|infraestructura|vida universitaria|biblioteca|deportes?\b|"
    r"con[oó]c[eé]\w*|admisi[oó]n|galer[ií]a|tour|recorrido|edificio|nuestra universidad|"
    r"la universidad|instituci[oó]n|laboratorios?|residencias?|comedor", re.I)

# The type of space, in the order the profile prefers them; the first that
# the photograph's words name is its type.
TIPOS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("laboratorio", re.compile(
        r"laborator|\blab\b|taller(?:es)?\b|simulaci[oó]n|simulador|estudio de (?:radio|tv|televisi)|"
        r"\bradio\b|sala de inform[aá]tica|makerspace|fab ?lab", re.I)),
    ("biblioteca", re.compile(r"biblioteca|sala de lectura|hemeroteca|mediateca|coworking|sala de estudio", re.I)),
    ("comedor", re.compile(r"comedor|cafeter[ií]a|buffet|\bbar\b|cantina|food ?court", re.I)),
    ("deportes", re.compile(
        r"deport|gimnasio|\bcancha|polideportivo|pileta|piscina|natatorio|campo de juego|playón", re.I)),
    ("aula", re.compile(r"\baulas?\b|anfiteatro|auditorio|sal[oó]n de (?:actos|clases)|sala de clases?|aula magna", re.I)),
    ("campus", re.compile(
        r"campus|edificio|fachada|\bsede\b|entrada|ingreso|frente\b|parque|patio|jard[ií]n|predio|"
        r"vista a[eé]rea|a[eé]rea|pabell[oó]n|hall\b|ciudad universitaria|facultad de|rectorado|claustro", re.I)),
    ("otro", re.compile(r"residencia|alojamiento|espacio de recreaci[oó]n|sala de juegos", re.I)),
)
PRIORIDAD = ("campus", "aula", "laboratorio", "biblioteca", "comedor", "deportes", "otro")

# Words that make a photograph something else than a space: a mark, a piece
# of print, a screen, a portrait, a ceremony, a stock picture.
NO_ES_UN_ESPACIO = re.compile(
    r"logo|escudo|isotipo|icono|\bicon\b|favicon|banner|flyer|afiche|placa\b|placeholder|captura|screenshot|"
    r"avatar|perfil|retrato|autoridad|rector(?:a)?\b|decan[oa]|vicerrector|presidente|director(?:a)?\b|"
    r"egresad|graduaci|graduad|colaci[oó]n|acto\b|ceremonia|jura\b|diploma|"
    r"congreso|jornada|charla|conferencia|seminario|webinar|evento|inauguraci|visita de|"
    r"shutterstock|istock|freepik|depositphotos|adobestock|unsplash|pexels|gettyimages|\bstock\b|"
    r"mapa\b|plano\b|\bqr\b|whatsapp|instagram|facebook|twitter|youtube|linkedin|"
    r"slider|\bslide|header|footer|fondo|background|\bbkg\b|sprite|pattern|textura|bot[oó]n|botones|"
    r"virtual|online|a distancia|d[ií]a del|semana de|brindis|cena\b|video|portada|concept|premio|grupal|"
    r"equipo\b|staff", re.I)

# The pages that tell news: a photograph there shows what happened that day
# (a visit, a ceremony, a competition), not the place.
NOTICIAS = re.compile(r"/(?:noticias?|novedades|prensa|actualidad|revista|blog|agenda|eventos?|ubanoticias|"
                      r"ubaciencia|comunicados?|medios)(?:/|$)", re.I)
# A strip wider than this is a page's banner, which carries its own text.
PROPORCION_MAXIMA = 2.2

EXTENSION = re.compile(r"\.(jpe?g|png|webp)$", re.I)
# A content manager's reduced copies: "foto-300x200.jpg", "foto-scaled.jpg",
# "foto-1024x683-1.jpg".
COPIA_REDUCIDA = re.compile(r"-(?:\d{2,4}x\d{2,4}|scaled|e\d{10,})(?=(?:-\d)?\.\w+$)", re.I)
CREDITO = re.compile(r"(?:foto(?:graf[ií]a)?s?|cr[eé]dito|imagen)\s*:\s*([^|\n]{2,60})|©\s*([^|\n]{2,60})", re.I)

MINIMO_ANCHO = 1000


@dataclass
class Candidata:
    url_imagen: str
    pagina: str
    tipo: str
    texto_alternativo: str
    epigrafe: str
    credito: str
    sede: str
    variantes: list[str] = field(default_factory=list)
    # The type came from the page about one space, not from the photograph's
    # own words; such a photograph is kept only when it is a landscape view.
    por_la_pagina: str = ""


def desenvolver(url: str) -> str:
    """The file itself, for an address that serves it through a resizer."""
    partes = urlparse(url)
    if partes.path.endswith("/_next/image") and (interna := parse_qs(partes.query).get("url")):
        return urljoin(url, interna[0])
    return url


def palabras_del_archivo(url: str) -> str:
    nombre = unquote(urlparse(url).path.rsplit("/", 1)[-1])
    nombre = COPIA_REDUCIDA.sub("", EXTENSION.sub("", nombre))
    return clean_text(re.sub(r"[-_.+]+|\d+", " ", nombre)) or ""


def tipo_de(*textos: str) -> str | None:
    juntos = " ".join(t for t in textos if t)
    if not juntos or NO_ES_UN_ESPACIO.search(juntos):
        return None
    for tipo, patron in TIPOS:
        if patron.search(juntos):
            return tipo
    return None


def original_de(url: str) -> str:
    """The full-size file a content manager's reduced copy was made from:
    WordPress's "-300x200" or "-scaled" copies, Drupal's image styles."""
    partes = urlparse(url)
    camino = re.sub(r"/styles/[^/]+/(public|private)/", "/", partes.path)
    return partes._replace(path=COPIA_REDUCIDA.sub("", camino), query="", fragment="").geturl()


def _mayor_del_srcset(srcset: str, base: str) -> str | None:
    mejor, ancho_mejor = None, -1
    for parte in srcset.split(","):
        trozos = parte.strip().split()
        if not trozos:
            continue
        ancho = int(trozos[1][:-1]) if len(trozos) > 1 and re.fullmatch(r"\d+w", trozos[1]) else 0
        if ancho > ancho_mejor:
            mejor, ancho_mejor = urljoin(base, trozos[0]), ancho
    return mejor


def _epigrafe(img: Tag) -> str:
    figura = img.find_parent("figure")
    if figura is not None and (leyenda := figura.find("figcaption")):
        return clean_text(leyenda.get_text(" ")) or ""
    for padre in (img.parent, img.parent.parent if img.parent else None):
        if padre is not None and (leyenda := padre.find(class_=re.compile(r"caption|epigrafe|leyenda", re.I))):
            return clean_text(leyenda.get_text(" ")) or ""
    return ""


def _sede_de(soup: BeautifulSoup, img: Tag) -> str:
    """The campus a photograph belongs to, when the heading above it names one."""
    encabezado = img.find_previous(re.compile(r"^h[1-4]$"))
    texto = clean_text(encabezado.get_text(" ")) if encabezado else ""
    hallada = re.search(r"\b(?:sede|campus)\s+([A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ .]{2,40})", texto or "")
    return clean_text(hallada.group(0)) if hallada else ""


def tema_de(soup: BeautifulSoup, pagina: str) -> tuple[str, str] | None:
    """The space a page is about, when its address and its main heading both
    name one (the home page and a page about many things name none)."""
    camino = unquote(urlparse(pagina).path).strip("/")
    if not camino:
        return None
    ultimo = camino.rsplit("/", 1)[-1].replace("-", " ").replace("_", " ")
    h1 = soup.find("h1")
    titulo = clean_text(h1.get_text(" ")) if h1 else ""
    tipo = tipo_de(ultimo)
    if not titulo or tipo is None or tipo_de(titulo) != tipo or len(titulo.split()) > 8:
        return None
    return tipo, titulo


def imagenes_de(html: str, pagina: str) -> list[Candidata]:
    """The photographs of a page whose own words, or else the page's, name
    the space they show."""
    soup = BeautifulSoup(html, "html.parser")
    tema = tema_de(soup, pagina)
    for basura in soup(["header", "footer", "nav", "script", "noscript", "style"]):
        basura.decompose()
    vistas: dict[str, Candidata] = {}
    for img in soup.find_all("img"):
        fuentes = [img.get(a) for a in ("data-src", "data-lazy-src", "data-original", "src") if img.get(a)]
        srcset = img.get("data-srcset") or img.get("srcset") or ""
        url = _mayor_del_srcset(srcset, pagina) if srcset else None
        url = url or (urljoin(pagina, fuentes[0]) if fuentes else None)
        enlace = img.find_parent("a")
        if enlace is not None and EXTENSION.search(urlparse(enlace.get("href") or "").path):
            url = urljoin(pagina, enlace["href"])
        url = desenvolver(url) if url else url
        if not url or not url.startswith("http") or not EXTENSION.search(urlparse(url).path):
            continue
        alt = clean_text(img.get("alt") or "") or ""
        titulo = clean_text(img.get("title") or "") or ""
        epigrafe = _epigrafe(img)
        # The photograph's own classes and those of the few boxes around it:
        # a slider's or a header's picture carries text printed over it.
        cercanos = [img, *list(img.parents)[:4]]
        clases = " ".join(" ".join(t.get("class") or []) + " " + (t.get("id") or "") for t in cercanos)
        if NO_ES_UN_ESPACIO.search(clases):
            continue
        tipo = tipo_de(alt, titulo, epigrafe, palabras_del_archivo(url))
        por_la_pagina = ""
        if tipo is None and tema and not NO_ES_UN_ESPACIO.search(" ".join((alt, titulo, epigrafe, url))):
            tipo, por_la_pagina = tema
        if tipo is None:
            continue
        credito = CREDITO.search(epigrafe or "")
        clave = original_de(url)
        anterior = vistas.get(clave)
        if anterior is None:
            vistas[clave] = Candidata(clave, pagina, tipo, alt or titulo, epigrafe,
                                      clean_text(next(g for g in credito.groups() if g)) if credito else "",
                                      _sede_de(soup, img), [url], por_la_pagina)
        else:
            anterior.variantes.append(url)
    return list(vistas.values())


def enlaces_a_espacios(html: str, pagina: str, propio: str) -> list[str]:
    """The links of a page to the site's pages about its spaces."""
    soup = BeautifulSoup(html, "html.parser")
    hallados: list[str] = []
    for a in soup.find_all("a", href=True):
        destino = urljoin(pagina, a["href"]).split("#")[0]
        if not destino.startswith("http") or not urlparse(destino).netloc.endswith(propio):
            continue
        if re.search(r"\.(pdf|jpe?g|png|docx?|xlsx?|zip)$", destino, re.I) or NOTICIAS.search(urlparse(destino).path):
            continue
        if PAGINAS.search(a.get_text(" ") or "") or PAGINAS.search(unquote(urlparse(destino).path).replace("-", " ")):
            if destino not in hallados:
                hallados.append(destino)
    return hallados


def descripcion(c: Candidata) -> str:
    """The photograph's own words, as the university wrote them."""
    texto = c.epigrafe or c.texto_alternativo or c.por_la_pagina or palabras_del_archivo(c.url_imagen)
    texto = CREDITO.sub("", texto).strip(" .-|")
    return (texto[:1].upper() + texto[1:])[:140] if texto else ""
