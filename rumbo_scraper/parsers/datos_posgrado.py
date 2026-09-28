"""The degree, duration and modality a postgraduate programme's page states.

A postgraduate page says its degree the way a grado page does, as a label
("Título: Magíster en Finanzas", "Título que otorga: Especialista en ...")
or in a sentence ("obtendrás el título de Doctor/a en ..."); only the
degree words differ. The degree is kept only if it is this programme's:
most of the words of its subject have to be there, because a faculty's page
of one master's often names its sister specialisation's degree too.

Duration and modality are read from the page's labelled facts
(`generico.leer_datos`), as for any programme.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from rumbo_scraper.normalizers.text import clean_text, comparison_key
from rumbo_scraper.parsers import generico
from rumbo_scraper.parsers.titulo import _FRASE

# Where the line stops saying the degree. Unlike a grado degree's, a comma is
# not cut here: "Especialista en Divulgación de la Ciencia, la Tecnología y
# la Innovación" is one name.
_CORTE = re.compile(r"\s*(?:[.;]\s|\.$|\(|\s[-–]\s|\s\|\s|\s+con\s+validez|\s+duraci[óo]n\b|"
                    r"\s+reconocimiento\b|\s+res(?:oluci[óo]n)?\.?\s)")

_UN_TITULO = re.compile(r"(?i)^(?:mag[íi]ster|m[áa]ster|especialista|doctor(?:a|/a|\(a\))?)\s+(?:en|de)\s+\S")
_TIPO = re.compile(r"(?i)^(?:carrera de\s+)?(?:doctorado|maestr[íi]a|mag[íi]ster|m[áa]ster|especializaci[óo]n)"
                   r"\s+(?:en|de|del)\s+")
_VACIAS = frozenset("para como desde sobre entre hacia orientacion mencion".split())


def _palabras(texto: str) -> set[str]:
    return {p for p in re.findall(r"[a-z]{4,}", comparison_key(texto)) if p not in _VACIAS}


def limpio(texto: str) -> str | None:
    """The degree as a name: cut where the line goes on, and not shouted."""
    from rumbo_scraper.parsers.posgrados_listas import _titulo

    texto = _CORTE.split(clean_text(texto), maxsplit=1)[0]
    # What the sentence goes on to say: ", se despliegan a lo largo de...",
    # " expedido por la Universidad", ".: Requisitos a cumplir".
    # A comma that goes on with the list of the name ("la Ciencia, la
    # Tecnología y la Innovación", ", mención ...") stays.
    # A colon stays when the name goes on after it ("Lenguas Extranjeras:
    # Problemáticas Sociodidácticas"), and cuts where a sentence starts
    # ("Especialista en Neurociencias: Requisitos a cumplir para...").
    texto = re.split(r"\.\s*:|:\s+(?=\S+\s+[a-záéíóúñ])|,\s+(?!(?:(?:el|la|los|las|y|e)\s+)?[A-ZÁÉÍÓÚÑ]|(?:con\s+)?orientaci[óo]n|menci[óo]n)|"
                     r"\s+(?:expedido|otorgado|emitido)\b", texto, maxsplit=1)[0].strip(" .:;,-–\"'“”")
    if not _UN_TITULO.match(texto) or len(texto) > 120 or len(texto.split()) > 18:
        return None
    # "Magister en Gestión del": the line broke before the subject ended.
    if re.search(r"(?i)\s(?:en|de|del|la|el|los|las|y|e|o|con|para|menci[óo]n)$", texto):
        return None
    if texto.isupper():
        texto = _titulo(texto)
    return texto[0].upper() + texto[1:]


def _lineas(html: str) -> list[str]:
    """The page's lines of content, a label joined to the value under it.

    Menus, header and footer go; a <form> stays, because an ASP.NET site
    wraps the whole page in one. A table's rows become "Header: cell" lines,
    so a table of "Título | Duración" reads like labelled fields.
    """
    soup = BeautifulSoup(html or "", "html.parser")
    for parte in soup.find_all(["nav", "header", "footer", "script", "style", "noscript"]):
        parte.decompose()
    for tabla in soup.find_all("table"):
        filas = tabla.find_all("tr")
        encabezados = [clean_text(c.get_text(" ", strip=True)) for c in filas[0].find_all(["th", "td"])] \
            if filas else []
        lineas = []
        for fila in filas[1:]:
            celdas = [clean_text(c.get_text(" ", strip=True)) for c in fila.find_all(["th", "td"])]
            if len(celdas) == len(encabezados):
                lineas += [f"{e}: {v}" for e, v in zip(encabezados, celdas) if e and v]
        if lineas:
            tabla.replace_with(soup.new_string("\n" + "\n".join(lineas) + "\n"))
    texto = (soup.body or soup).get_text("\n")
    # "Título de Posgrado" as a heading, the degree in the next element.
    texto = re.sub(r"(?im)^(\s*(?:t[íi]tulos?|duraci[óo]n|modalidad|grado\s+(?:acad[ée]mico\s+)?otorgado)"
                   r"[^:\n]{0,40}):?\s*\n+\s*", r"\1: ", texto)
    # "Título con reconocimiento oficial y validez nacional que otorga:" and,
    # on the next line, the degree.
    texto = re.sub(r"(?im)^(\s*[^\n]{0,90}\b(?:t[íi]tulo|otorga)[^\n]{0,90}:)\s*\n+\s*", r"\1 ", texto)
    return [clean_text(l) for l in texto.split("\n") if clean_text(l)]


_ROTULO_DE_TITULO = re.compile(
    r"(?i)(?:^t[íi]tulos?(?:\s+[^:]{0,40})?|^grado\s+(?:acad[ée]mico\s+)?otorgado|"
    r"\b(?:t[íi]tulo|otorga)[^:]{0,90}):\s*(.+)")
# "... otorga validez al título de Magíster en Historia Contemporánea."
_EN_UNA_FRASE = re.compile(r"(?i)\bt[íi]tulo\s+de\s+((?:mag[íi]ster|m[áa]ster|especialista|doctor)\b.+)")
_ROTULO_DE_DURACION = re.compile(r"(?i)^duraci[óo]n(?:\s+[^:]{0,40})?:\s*(.+)")
_ROTULO_DE_MODALIDAD = re.compile(r"(?i)^modalidad(?:\s+[^:]{0,40})?:\s*(.+)")


def es_suyo(titulo: str, programa: str) -> bool:
    """Whether the degree names most of the programme's subject."""
    tema = _palabras(_TIPO.sub("", programa))
    return bool(tema) and len(_palabras(titulo) & tema) * 2 >= len(tema)


def titulo_de_posgrado(lineas: list[str], programa: str) -> str | None:
    """The one postgraduate degree the page gives that is this programme's."""
    hallados: dict[str, str] = {}
    for linea in lineas:
        for patron in (_ROTULO_DE_TITULO, _FRASE, _EN_UNA_FRASE):
            for match in patron.finditer(linea):
                titulo = limpio(match.group(1))
                if titulo:
                    hallados.setdefault(comparison_key(titulo), titulo)
    propios = [t for t in hallados.values() if es_suyo(t, programa)]
    return propios[0] if len(propios) == 1 else None


def _primero(lineas: list[str], patron: re.Pattern, leer) -> object:
    for linea in lineas:
        match = patron.match(linea)
        if match and (valor := leer(match.group(1))) is not None:
            return valor
    return None


def nombra_el_programa(html: str, programa: str) -> bool:
    """Whether the page's content writes the programme's name."""
    return comparison_key(programa) in comparison_key(" ".join(_lineas(html)))


def minimo_de_meses(programa: str) -> int:
    """The fewest months a programme of its kind can last: a doctorate is not
    done in a year, nor a master's in a semester."""
    clave = comparison_key(programa)
    if clave.startswith("doctorado"):
        return 24
    if re.match(r"(?:maestria|magister|master|mba)\b", clave):
        return 12
    return 6


def datos_de_posgrado(html: str, programa: str) -> dict[str, object]:
    """What the page says of the programme: degree, months, modality."""
    lineas = _lineas(html)
    meses = _primero(lineas, _ROTULO_DE_DURACION, generico.duracion_meses)
    return {
        "titulo_otorgado": titulo_de_posgrado(lineas, programa),
        "duracion_meses": meses if meses and minimo_de_meses(programa) <= meses <= 72 else None,
        "modalidad": _primero(lineas, _ROTULO_DE_MODALIDAD, generico.modalidad),
    }
