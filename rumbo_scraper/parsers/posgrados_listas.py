"""The postgraduate programmes a university lists on one page.

Most national universities keep a page with every doctorate, master's and
specialisation they teach, each written out in full and most linking to a
page of its own: "Maestría en Ciencias Agrarias", "Doctorado en Física". A
postgraduate degree, like a grado one, has a name the Ministry closes: it
starts with the kind of degree and then says what it is in. So a line of such
a page that starts that way, and is not a sentence, is a programme.

Only the three degrees CONEAU accredits are read. A "diplomatura" or a
"curso de posgrado" is announced on the same pages and is a course, not a
postgraduate career; the national catalogue keeps them out.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, replace
from difflib import SequenceMatcher
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from rumbo_scraper.normalizers.text import clean_text, comparison_key

TIPOS = (
    (re.compile(r"^doctorado\b"), "Doctorado"),
    (re.compile(r"^(?:maestria|magister|master|mba)\b"), "Maestría"),
    (re.compile(r"^(?:carrera de )?especializacion\b"), "Especialización"),
)

# The kind of degree, then what it is in: "Maestría en", "Doctorado de",
# "Especialización en", with at most two qualifiers between ("Maestría
# Interinstitucional en", "Doctorado Latinoamericano en"). Any other word
# there is a card that ran the kind into a description: "Maestría Gestión
# del Diseño para los Desarrollos Regionales Esta carrera...".
_CALIFICATIVOS = (r"interinstitucional|intrainstitucional|latinoamerican[oa]|"
                  r"internacional|binacional|regional|academic[oa]|profesional|"
                  r"conjunt[oa]|cooperativ[oa]|personalizad[oa]|estructurad[oa]|"
                  r"integrad[oa]|universitari[oa]|semiestructurad[oa]|"
                  # "Especialización Docencia en Educación Superior" (UNRC):
                  # the subject's first word, written without its "en".
                  r"docencia")
# A private university also writes "Magíster en", "Master en" and "MBA".
_UN_NOMBRE = re.compile(
    r"^(?:(?:carrera de )?(?:doctorado|maestria|magister|master|especializacion)"
    rf"(?:\s+(?:{_CALIFICATIVOS})){{0,2}}\s+(?:en|de|del|sobre)\s+\S|mba\b|"
    r"master (?:in|of) \S)")
# What turns a name into news, a call or a section about the degree.
_NO_ES_EL_NOMBRE = re.compile(
    r"\b(?:inscripci|preinscrip|convocatoria|cohorte|abierta|abiertas|"
    r"defensa|defendio|tesis de|tesista|egresad|graduad|becas?|beca de|"
    r"reglamento|resolucion(?! de conflictos)|ordenanza|acta|jornada|charla|seminario|curso|"
    r"programa de la materia|admision|arancel|cronograma|calendario|"
    r"horarios?|comite|consejo|director[a]? de|coordinador|aprobo|aprueba|"
    r"acredit[oa]|se dicta|inicia|comienza|comenzo|lanza|presenta|nueva|nuevo|"
    # A heading over a section lists kinds: "MBA y Maestrías".
    r"maestrias|especializaciones|doctorados|posgrados)\b")
# What a site writes after the name, on the same line: its accreditation,
# its category, its modality or the cohort open now.
_COLA = re.compile(
    r"(?i)\s*(?:[-–—|:(\[]\s*|\s)(?:acreditad[ao]|con acreditaci[óo]n|"
    r"categor[íi]a\b|cat\.\s|coneau|res(?:oluci[óo]n)?\.?\s*(?:n|cs|me|min)|"
    r"(?:modalidad|a distancia|virtual|presencial|semipresencial)\b|"
    r"cohorte|inscripci[óo]n|nueva cohorte|resfc\b|res\w*-\d|"
    # The start of the next intake, printed inside the link: "17 marzo".
    r"\d{1,2}\s+(?:de\s+)?(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
    r"septiembre|setiembre|octubre|noviembre|diciembre)\b|\(?\d{4}\)?\s*$).*$")
# An acronym after the name: "| MBA", "| GTec", "(MRS)", "- MAGNAGRO".
_SIGLA = re.compile(r"\s*(?:\s[-–—]\s+Sede\b.*|\|\s*[^|]{2,20}|\s-[a-z]{1,4}|[\-–—]\s*[A-ZÁÉÍÓÚÑ]{2,12}|"
                    r"[\-–—]\s*(?=\S*[A-Z]\S*[A-Z]|\S*/)\S{2,16}|"
                    r"\(\s*[A-ZÁÉÍÓÚÑ]{2,12}\s*\))\s*$")
# What a site puts in brackets after the name to say where or with whom it
# is taught: "(Sede Corrientes)", "(FHAyCS | Sede Paraná)", "(FCVyS - UNGS)",
# "(En conjunto con la Facultad de Humanidades)". A bracket that is part of
# the name, "(Operatoria Dental y Biomateriales)", says none of that.
_DONDE = re.compile(r"\s*\((?=[^()]*(?:\b[Ss]edes?\b|[Ff]acultad|[Ee]n conjunto|"
                    r"[Ff]ormaci[óo]n|[Cc]arrera|[Dd]istancia|[Vv]irtual|[Pp]resencial|"
                    # Its state: "(preinscripción online 2027)", "(en curso 2025-2026)".
                    r"[Pp]re-?ins?cripci|[Ii]nicio|[Ee]n curso|[Aa]biert[ao]|"
                    r"[Ii]nter-?institucional|[Ii]ntrainstitucional|"
                    r"\b[A-Z][a-zA-Z]*[A-Z][a-zA-Z]*\b))[^()]*\)\s*$")
# A footnote mark and what it points to: "... Oleaginosas * * Dictada en ...".
_NOTA = re.compile(r"\s+\*.*$")
# The subject in quotes, without its preposition: Maestría “Docencia Universitaria”.
_ENTRE_COMILLAS = re.compile(r"(?i)^((?:carrera de\s+)?(?:doctorado|maestr[íi]a|especializaci[óo]n))"
                             r"\s*[\"“”«]\s*([^\"“”»]+?)\s*[\"“”»]\s*$")
# The modality after a dash: "Especialización en Dirección de Empresas -
# Online". Only after a separator: "Docencia Híbrida" is a subject.
_MODALIDAD_DETRAS = re.compile(r"(?i)\s*[-–—|(]\s*(?:online|on line|blended|h[íi]brid[ao]|virtual|"
                               r"a distancia|presencial|semipresencial)\b.*$")
_ARTICULO = re.compile(r"\s+(?:en|de|del|y|la|el|los|las)$", re.I)
# A second degree in the same line: a card that lists two programmes, or one
# that follows the name with the title it gives ("Especialización en
# Bioinformática Especialista en Bioinformática"). The line is the first.
_OTRO_TITULO = re.compile(
    r"(?i)\s(?:doctorado|doctor(?:a)?\s+en|maestr[íi]a|mag[íi]ster|"
    r"especializaci[óo]n|especialista)\b")


@dataclass(frozen=True)
class PosgradoListado:
    nombre: str
    tipo: str
    url: str
    # The page the name was read from, where it is not the programme's own.
    fuente: str
    facultad: str | None = None


def nombre_de_posgrado(texto: str) -> tuple[str, str] | None:
    """The programme a line names, with its kind, or None.

    >>> nombre_de_posgrado("Maestría en Ciencias Agrarias - Acreditada CONEAU Cat. A")
    ('Maestría en Ciencias Agrarias', 'Maestría')
    >>> nombre_de_posgrado("Abierta la inscripción al Doctorado en Física") is None
    True
    """
    nombre = _NOTA.sub("", clean_text(texto.replace("\u200b", " ")))
    # A label before the name: "Segundo año | Magíster en Cine Documental".
    nombre = re.sub(r"(?i)^[^|]{2,20}\|\s*(?=(?:mag|maest|m[aá]ster|espec|doct))", "", nombre)
    # The title a card heads its programme with: "Especialista en X" is the
    # Especialización en X.
    nombre = re.sub(r"(?i)^especialista\s+en\b", "Especialización en", nombre)
    # And "Magíster en X", "Master en X" is the Maestría en X.
    nombre = re.sub(r"(?i)^(?:mag[íi]ster|m[áa]ster)\s+en\b", "Maestría en", nombre)
    comillas = _ENTRE_COMILLAS.match(nombre)
    if comillas:
        nombre = f"{comillas.group(1)} en {comillas.group(2)}"
    nombre = nombre.strip(" .,;:-–—•·*»›\"'“”")
    if nombre.count("“") > nombre.count("”"):
        nombre += "”"
    primero = re.match(r"(?i)(?:carrera de\s+)?\S+", nombre)
    otro = _OTRO_TITULO.search(nombre, primero.end() if primero else 0)
    if otro:
        # "MBA - Maestría en Dirección de Empresas": the acronym, then the name.
        antes = nombre[:otro.start()].strip(" -–—|:")
        nombre = (nombre[otro.start():].strip()
                  if re.fullmatch(r"[A-Z]{2,6}|(?i:m[aá]ster)", antes) else antes)
    # The bracket first: "(Carrera a distancia)" is not cut at "a distancia".
    nombre = _SIGLA.sub("", _COLA.sub("", _MODALIDAD_DETRAS.sub("", _DONDE.sub("", nombre))))
    nombre = clean_text(_DONDE.sub("", nombre)).strip(" .,;:-–—")
    nombre = _ARTICULO.sub("", nombre)
    if not 12 <= len(nombre) <= 150 or len(nombre.split()) > 20:
        return None
    if any(marca in nombre for marca in "!¡?¿") or nombre.count(".") > 1:
        return None
    clave = comparison_key(nombre)
    if not _UN_NOMBRE.match(clave) or _NO_ES_EL_NOMBRE.search(clave):
        return None
    for patron, tipo in TIPOS:
        if patron.match(clave):
            # "Carrera de Especialización en X" is the Especialización en X.
            nombre = re.sub(r"(?i)^carrera de\s+", "", nombre)
            # A name shouted whole or in part: "ESPECIALIZACIÓN EN Sindicatura
            # Concursal", "ESPECIALIZACIÓN EN Producción Y AMBIENTES".
            letras = [c for c in nombre if c.isalpha()]
            if sum(c.isupper() for c in letras) > len(letras) / 2 or \
                    re.match(r"^\S*[A-ZÁÉÍÓÚ]{4,}\s+EN\b", nombre):
                nombre = _titulo(nombre)
            # "MAESTRÍA en Educación": only the kind was shouted.
            primera, _, resto = nombre.partition(" ")
            if primera.isupper() and len(primera) > 3:  # not "MBA"
                nombre = f"{primera.capitalize()} {resto}"
            nombre = nombre[:1].upper() + nombre[1:]
            nombre = re.sub(r"\b(en|de) \1\b", r"\1", nombre)
            # "Maestría En Trabajo Social": a site's own title case.
            nombre = re.sub(r"^(\S+(?:\s+\S+)?) En ", r"\1 en ", nombre, count=1)
            return nombre, tipo
    return None


_MENORES = frozenset("en de del y e o u la el los las a al con para por sobre su sus".split())


def _titulo(nombre: str) -> str:
    """A name written in capitals, as a name: the site shouted it."""
    def palabra(i: int, original: str) -> str:
        p = original.lower()
        # An acronym has no vowel after its first letter: "UNRN", "FCEFyN".
        if len(p) >= 3 and not re.search(r"[aeiouáéíóú]", p[1:]):
            return original
        return p if i and p in _MENORES else p[:1].upper() + p[1:]
    return " ".join(palabra(i, p) for i, p in enumerate(nombre.split()))


def _del_sitio(url: str, dominios: tuple[str, ...]) -> bool:
    host = urlparse(url).hostname or ""
    return any(host == d or host.endswith("." + d) for d in dominios)


_BLOQUES = ("a", "li", "h1", "h2", "h3", "h4", "h5", "h6", "p", "td", "strong",
            "b", "span", "div", "option", "dt", "summary", "button")


# A card that writes the kind of degree apart from what it is in:
# <div class="card-subtitle">Maestría</div>
# <h3 class="card-title"><a href="...">Gestión del Diseño</a></h3>
_SOLO_EL_TIPO = re.compile(r"^(?:doctorado|maestria|especializacion)$")
_EDICION = re.compile(r"(?i)^\d+\s*[ªºa°]?\s*cohorte\s+(?:de|del)\s+")


def _nombres_de_la_tarjeta(elemento: Tag) -> list[tuple[str, Tag]]:
    """The full names a card gives by its kind and, beside it, the subjects.

    One subject follows the kind on a card; a menu puts one kind over a run
    of links of the same shape ("Especialización": Cirugía Buco Máxilo
    Facial, Diagnóstico por Imágenes, ...), and the kind applies to each.
    """
    if not _SOLO_EL_TIPO.match(comparison_key(elemento.get_text(" ", strip=True))):
        return []
    tipo = clean_text(elemento.get_text(" ", strip=True)).capitalize()
    primero = elemento.find_next_sibling()
    if not isinstance(primero, Tag):
        return []
    forma = (primero.name, tuple(primero.get("class") or ()))
    nombres = []
    for titulo in [primero, *primero.find_next_siblings()]:
        if (titulo.name, tuple(titulo.get("class") or ())) != forma:
            break
        tema = _EDICION.sub("", clean_text(titulo.get_text(" ", strip=True)))
        # A subject that is itself a kind of course is a card filed under
        # the wrong heading: "Maestría" over "Diplomatura en ...".
        if not tema or re.match(r"(?:en|de|del|diplomaturas?|cursos?|seminarios?|doctorados?|"
                                r"maestrias?|especializacion(?:es)?)\b", comparison_key(tema)):
            break
        nombres.append((f"{tipo} en {tema}", titulo))
    return nombres


# The degree a programme gives, printed where its name would be.
_UN_TITULO = re.compile(r"(?i)^(?:mag[íi]ster|m[áa]ster|especialista)\s+en\b")

# Two degrees over one subject: "Maestría y Especialización en Vínculos".
_DOS_TIPOS = re.compile(r"(?i)^(maestr[íi]a|especializaci[óo]n|doctorado)\s+y\s+"
                        r"(maestr[íi]a|especializaci[óo]n|doctorado)\s+(en\s+.+)$")


def leer_lista(html: str, pagina: str, dominios: tuple[str, ...],
               ambito: str | None = None, facultad: str | None = None,
               prefijo: str | None = None) -> list[PosgradoListado]:
    """Every programme a page lists, in the order it lists them.

    A name that links to a page of the university's own sites takes that page
    as its address; one written without a link, or linking elsewhere, takes
    the page it is listed on, which is the one that says it. ``ambito`` is a
    CSS selector for the part of the page that holds the list, where the menus
    around it list other things. ``prefijo`` is for a list that gives only
    the subjects under a heading that says the kind ("Carrera de
    Especialización bajo modalidad de Residencia: - Cardiología"): each
    "- Subject" line inside ``ambito`` is read as ``prefijo`` + subject.
    """
    # "&microtipo=" in a link is a query, not the entity "&micro": the
    # parser would turn it into "µtipo=".
    html = re.sub(r"&(?=[A-Za-z][A-Za-z0-9_]*=)", "&amp;", html)
    # A page that keeps each faculty's list in its script, as a template it
    # shows on a click: `<ul><li><a ...>Maestría en ...</a></li></ul>`.
    guardadas = [b for b in re.findall(r"`([^`]*)`", html)
                 if re.match(r"\s*<[a-z]", b) and re.search(r"<(?:li|a)\b", b)]
    if guardadas:
        html += "<div>" + "".join(guardadas) + "</div>"
    soup = BeautifulSoup(html, "html.parser")
    # A <small> is a label beside the name: "Cursos de posgrado" before it,
    # "Sede General Pico" after it.
    # The menus list everything, so they are dropped; but a page named with
    # ``ambito`` is read where it says, and a faculty that lists its
    # postgraduates only in a menu is read there.
    quitar = ["script", "style", "noscript", "small"]
    if not ambito:
        quitar += ["header", "footer", "nav"]
    for element in soup(quitar):
        element.decompose()
    raices: list[Tag] = soup.select(ambito) if ambito else [soup]
    leidos: list[tuple[Tag, str, str]] = []
    for raiz in raices:
        # The part named by ``ambito`` may be the heading itself.
        for elemento in [raiz, *raiz.find_all(_BLOQUES)]:
            if elemento.name not in _BLOQUES:
                continue
            texto = elemento.get_text(" ", strip=True)
            # A card that is only an image says the name in its link's title.
            if not texto and elemento.name == "a":
                texto = elemento.get("title") or ""
            if prefijo:
                tema = re.match(r"^[-–•]\s*([^()*\d]{4,70}?)\s*$", texto)
                texto = f"{prefijo} {tema.group(1)}" if tema else ""
            candidatos = _nombres_de_la_tarjeta(elemento) or [(texto, elemento)]
            dos = _DOS_TIPOS.match(clean_text(texto))
            if dos:
                candidatos = [(f"{dos.group(1)} {dos.group(3)}", elemento),
                              (f"{dos.group(2)} {dos.group(3)}", elemento)]
            for candidato, donde in candidatos:
                leido = nombre_de_posgrado(candidato)
                if leido:
                    titulo = bool(_UN_TITULO.match(clean_text(candidato)))
                    leidos.append((donde, *leido, titulo))
    # Only the innermost element that names a programme: the card around it
    # also carries "Abierto", "Más información" or the campus.
    # A page that names its programmes and prints under each the degree it
    # gives ("Magíster en Diabetes") names each twice: the degree goes.
    nombrados = [comparison_key(n) for _, n, _, titulo in leidos if not titulo]
    leidos = [(e, n, t, titulo) for e, n, t, titulo in leidos
              if not titulo or not any(comparison_key(n) == k or comparison_key(n).startswith(k + " ")
                                       for k in nombrados)]
    con_nombre = {id(e) for e, _, _, _ in leidos}
    encontrados: dict[str, PosgradoListado] = {}
    for elemento, nombre, tipo, _ in leidos:
        if any(id(d) in con_nombre for d in elemento.find_all(_BLOQUES)):
            continue
        clave = comparison_key(nombre)
        url = pagina
        enlace = _enlace(elemento, con_nombre)
        if enlace is not None:
            destino = urljoin(pagina, clean_text(enlace["href"])).split("#")[0]
            # A document is not a page the verifier can read the name on.
            if destino.startswith("http") and _del_sitio(destino, dominios) \
                    and not re.search(r"\.(?:jpe?g|png|gif|pdf|docx?|xlsx?)$", destino, re.I):
                url = destino
                # The home page of a faculty's site says nothing about the
                # programme; the list does.
                if urlparse(destino).path.rstrip("/") in ("", "/index.php", "/index.html"):
                    url = pagina
        clave = comparison_key(nombre)
        anterior = encontrados.get(clave)
        # A name met again with its own link beats the bare one.
        if anterior is None or (anterior.url == pagina and url != pagina):
            encontrados[clave] = PosgradoListado(nombre, tipo, url, pagina, facultad)
    # One programme written two ways, both linking to its page: "Especializacion
    # en Gestión de Vinculación Tecnologíca" and "Especialización en Gestión y
    # Vinculación Tecnológica". The one with more of its accents stays.
    for clave, programa in list(encontrados.items()):
        for otra, gemelo in list(encontrados.items()):
            if otra == clave or clave not in encontrados or otra not in encontrados \
                    or programa.url == pagina or programa.url != gemelo.url \
                    or SequenceMatcher(None, clave, otra).ratio() < 0.9:
                continue
            peor = min((clave, programa), (otra, gemelo), key=lambda par: (
                sum(not c.isascii() for c in par[1].nombre), len(par[1].nombre)))
            del encontrados[peor[0]]
    # A page three programmes link to is a faculty's or an office's, not the
    # page of any of them; the list names them as well as it does.
    veces = Counter(p.url for p in encontrados.values())
    return [p if p.url == pagina or veces[p.url] < 3 else replace(p, url=pagina)
            for p in encontrados.values()]


def _destinos(elemento: Tag) -> set[str]:
    return {clean_text(a["href"]) for a in elemento.find_all("a", href=True)
            if not clean_text(a["href"]).startswith(("#", "mailto:", "tel:", "javascript:"))}


def _enlace(elemento: Tag, con_nombre: set[int]) -> Tag | None:
    """The link that leads to the programme a name belongs to.

    The name's own link, the one link inside it, or the link it sits in; else
    the card around it, when every link the card holds goes to the same page
    (a picture and a "Más información" under a heading with no link). A card
    that links to two places, or names a second programme, links to more
    than the programme: a faculty's section, with its site's link.
    """
    if elemento.name == "a" and elemento.get("href"):
        return elemento
    if len(_destinos(elemento)) == 1:
        return elemento.find("a", href=True)
    padre = elemento.find_parent("a", href=True)
    if padre is not None:
        return padre
    if _destinos(elemento):
        return None
    # The name itself, and what wraps it, are not a second programme.
    suyos = {id(elemento), *(id(d) for d in elemento.find_all(_BLOQUES)),
             *(id(a) for a in elemento.parents)}
    for antecesor in list(elemento.parents)[:4]:
        destinos = _destinos(antecesor)
        otros = sum(id(d) in con_nombre and id(d) not in suyos
                    for d in antecesor.find_all(_BLOQUES))
        if len(destinos) > 1 or otros:
            return None
        if destinos:
            return antecesor.find("a", href=True)
    return None
