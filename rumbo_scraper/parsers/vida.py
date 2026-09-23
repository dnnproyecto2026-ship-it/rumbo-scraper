"""Reading what a university publishes about student life.

Scholarships, student services, sport and culture, housing and the exchange
programmes are the five sections of the contract that no career page ever
fills, and every one of the fifteen sites keeps them in the same shape: a page
per topic, linked from the home page by a word that names the topic, holding a
list of items with a heading and a sentence under it.

That shape is read here once, for every university, instead of fifteen times.
The topic of a page is decided by the words the university itself used to link
it, and an item is only kept when the page gives it a name; a page of prose
about a topic yields nothing, which is the right answer for a university that
writes about its scholarships without listing them.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from rumbo_scraper.normalizers.text import clean_text, comparison_key
from rumbo_scraper.normalizers.url import is_official_url

# The five topics and the words a site uses to link each one. A link is
# assigned to the first topic that recognises it, so the order matters: a
# "beca de intercambio" is a scholarship before it is an exchange.
TOPICS: tuple[tuple[str, str], ...] = (
    ("becas", r"beca[s]?\b|ayuda econ[óo]mica|financiamiento"),
    ("alojamiento", r"residencia|alojamiento|vivienda|hospedaje"),
    ("programas_internacionales",
     r"internacional|intercambio|movilidad|study abroad|extranjero"),
    ("actividades_extracurriculares",
     r"deporte|cultura|coro|orquesta|extracurricular|vida universitaria|"
     r"centro de estudiantes|voluntariado"),
    ("servicios_estudiantiles",
     r"servicios? (al |para |de )?(estudiante|alumno)|bienestar|salud estudiantil|"
     r"orientaci[óo]n|biblioteca|tutor[íi]a|discapacidad|accesibilidad|"
     r"empleo|bolsa de trabajo|pasant[íi]a"),
)

# A link that names a topic but leads somewhere else: a career about sport, a
# news item about a scholarship, a form.
_NOT_A_TOPIC_PAGE = re.compile(
    r"(?i)/(noticias?|novedades|eventos?|agenda|prensa|blog|carreras?|"
    r"licenciatura|posgrado|maestria|doctorado|inscripci|formulario|login)\b"
)


def _soup(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style", "noscript"]):
        element.decompose()
    return soup


def discover_topics(html: str, page_url: str, domain: str) -> dict[str, list[str]]:
    """Read the pages the site links for each topic of student life."""
    found: dict[str, list[str]] = {topic: [] for topic, _ in TOPICS}
    for anchor in _soup(html).find_all("a", href=True):
        label = clean_text(anchor.get_text(" ", strip=True))
        if not label or len(label) > 70:
            continue
        url = urljoin(page_url, clean_text(anchor["href"])).split("#")[0]
        if not is_official_url(url, domain, require_https=False):
            continue
        if _NOT_A_TOPIC_PAGE.search(urlparse(url).path):
            continue
        for topic, pattern in TOPICS:
            if not re.search(pattern, label, re.I):
                continue
            if url not in found[topic]:
                found[topic].append(url)
            break
    return found


# What a page prints that is not the name of anything it offers.
_NOT_AN_ITEM = re.compile(
    r"(?i)^(inicio|home|contacto|men[úu]|buscar|ver m[áa]s|leer m[áa]s|"
    r"volver|siguiente|anterior|compartir|imprimir|descargar|suscrib|"
    r"cookies?|pol[íi]tica|t[ée]rminos|copyright|todos los derechos|"
    r"seguinos|seguí|newsletter|ingresar|iniciar sesi[óo]n)"
)


# Whether an item belongs to the topic of the page that lists it. A page
# about scholarships also carries its news and the names of the people
# quoted on it, and neither is a scholarship.
CLASSIFIERS = {
    "becas": lambda text: scholarship_kind(text),
    "actividades_extracurriculares": lambda text: activity_kind(text),
    "servicios_estudiantiles": lambda text: service_kind(text),
    "programas_internacionales": lambda text: exchange_kind(text),
    "alojamiento": lambda text: housing_kind(text),
}


def read_items(html: str, topic: str | None = None) -> list[dict[str, str]]:
    """Read the items a topic page lists, each with the sentence beside it.

    An item is a heading with text under it that the vocabulary of the topic
    recognises. A page that has no headings has no items, and a heading the
    topic does not recognise is the news, the name of a person or a section of
    the site -- all of which a page about scholarships also prints.
    """
    soup = _soup(html)
    for element in soup(["nav", "footer", "header", "aside", "form"]):
        element.decompose()
    items: list[dict[str, str]] = []
    seen: set[str] = set()
    for heading in soup.find_all(["h2", "h3", "h4"]):
        name = clean_text(heading.get_text(" ", strip=True))
        if not name or len(name) < 4 or len(name) > 90 or _NOT_AN_ITEM.match(name):
            continue
        if comparison_key(name) in seen:
            continue
        classify = CLASSIFIERS.get(topic or "")
        # The name is classified on its own. Classifying it together with the
        # paragraph under it made every name on the page inherit the topic, so
        # a student quoted about their exchange became an exchange programme.
        kind = classify(name) if classify else None
        if classify and not kind:
            continue
        description = _text_under(heading) or ""
        seen.add(comparison_key(name))
        items.append({"titulo": name, "descripcion": description, "tipo": kind or ""})
    return items


def _text_under(heading: Any) -> str | None:
    """The sentence a page prints under a heading, before the next one."""
    for node in heading.find_all_next():
        if node.name in ("h1", "h2", "h3", "h4"):
            return None
        if node.name in ("p", "li"):
            text = clean_text(node.get_text(" ", strip=True))
            if len(text) >= 40:
                return text[:600]
    return None


# What a scholarship covers, as the sites name it.
_SCHOLARSHIP_KINDS = (
    (r"m[ée]rito|promedio|excelencia|acad[ée]mic", "Mérito"),
    (r"deport", "Deportiva"),
    (r"socioecon[óo]mic|necesidad|ayuda", "Socioeconómica"),
    (r"arancel|descuento|matr[íi]cula", "Arancel"),
)
_PERCENTAGE = re.compile(r"(\d{1,3})\s*%")


def scholarship_kind(text: str) -> str | None:
    key = comparison_key(text)
    for pattern, kind in _SCHOLARSHIP_KINDS:
        if re.search(pattern, key):
            return kind
    return None


def percentage(text: str) -> float | None:
    """The share of the fee a scholarship covers, when the page states one."""
    values = [int(value) for value in _PERCENTAGE.findall(text or "")]
    values = [value for value in values if 0 < value <= 100]
    return float(max(values)) if values else None


_ACTIVITY_KINDS = (
    (r"deport|f[úu]tbol|b[áa]squet|v[óo]ley|rugby|nataci[óo]n|ajedrez|tenis", "Deporte"),
    (r"coro|orquesta|m[úu]sica|teatro|cine|arte|cultura|danza", "Cultura"),
    (r"voluntariado|solidari|social", "Acción social"),
    (r"centro de estudiantes|representaci[óo]n", "Representación estudiantil"),
)


def activity_kind(text: str) -> str | None:
    key = comparison_key(text)
    for pattern, kind in _ACTIVITY_KINDS:
        if re.search(pattern, key):
            return kind
    return None


_SERVICE_KINDS = (
    (r"biblioteca", "Biblioteca"),
    (r"salud|m[ée]dic|psicol[óo]g", "Salud"),
    (r"empleo|bolsa de trabajo|pasant[íi]a|laboral|carrera profesional", "Empleo"),
    (r"tutor|orientaci[óo]n|apoyo|acompa[ñn]amiento", "Apoyo académico"),
    (r"discapacidad|accesibilidad|inclusi[óo]n", "Accesibilidad"),
    (r"idioma|lenguas", "Idiomas"),
)


def service_kind(text: str) -> str | None:
    key = comparison_key(text)
    for pattern, kind in _SERVICE_KINDS:
        if re.search(pattern, key):
            return kind
    return None


_EXCHANGE_KINDS = (
    (r"doble titulaci[óo]n|doble grado", "Doble titulación"),
    (r"intercambio|movilidad", "Intercambio"),
    (r"pasant[íi]a|pr[áa]ctica", "Pasantía internacional"),
    (r"verano|summer|corto", "Programa corto"),
)


def exchange_kind(text: str) -> str | None:
    key = comparison_key(text)
    for pattern, kind in _EXCHANGE_KINDS:
        if re.search(pattern, key):
            return kind
    return None


_HOUSING_KINDS = (
    (r"residencia universitaria|residencia propia|campus", "Residencia universitaria"),
    (r"residencia|hospedaje|hostel", "Residencia"),
    (r"alojamiento|vivienda|departamento|familia", "Orientación e intermediación"),
)


def housing_kind(text: str) -> str | None:
    key = comparison_key(text)
    for pattern, kind in _HOUSING_KINDS:
        if re.search(pattern, key):
            return kind
    return None


_MAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def contact_in(text: str) -> str | None:
    match = _MAIL.search(text or "")
    return match.group(0) if match else None
