"""The academic unit a career page says the career belongs to.

The same career is a different career in a business school and in a faculty
of medicine, and most sites say which one on the career's own page -- but
only in a few places, and the rest of the page names every unit the
university has: the footer, the menu, the list of "other careers". So the
unit is read only where a page speaks of itself:

- the ``<title>`` and the site name (``og:site_name``): a faculty with a
  site of its own signs every page with it ("Carreras - Facultad de
  Ingeniería - UNMdP");
- the breadcrumb: "Inicio > Facultad de Ciencias Médicas > Medicina";
- the headings above the career's name.

A page that names two different units in those places is left alone: which of
the two is the career's is a guess. A unit the university already published
is preferred over a new name, and a new name is taken only from the title,
the site name or the breadcrumb, never from a heading alone.

When none of those names a unit, the body of the page -- without its menu,
header and footer -- is read, more strictly: a page about Bioingeniería at the
ITBA mentions the engineering faculty of the UBA, and one about Abogacía at
UBP the law faculty of Córdoba, and one at UNLaM a department of a news item
beside it. The body gives a unit only when it names one unit, at least twice,
and no other -- and, if the university published its units, one of those.

None of this is read off a page that is not the career's: the title or the
main heading has to name the career (`es_la_pagina_de`). Favaloro's
"Bioquímica" links to its page of short courses.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

from rumbo_scraper.normalizers.text import clean_text, comparison_key

_TIPOS = {
    "facultad": "Facultad",
    "escuela": "Escuela",
    "departamento": "Departamento",
    "instituto": "Instituto",
}

# "Facultad de Ciencias Médicas", "Escuela de Negocios", "Departamento de
# Artes Dramáticas", "Instituto de Ciencias de la Salud". The name runs until
# the sign or the word that ends it in a title or a breadcrumb.
_UNA_UNIDAD = re.compile(
    r"\b(Facultad|Escuela|Departamento|Instituto)\s+(?:de\s+(?:la\s+|las\s+|los\s+)?|del\s+|en\s+)"
    r"([A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñü]*(?:[ ,]+(?:y|e|de|del|la|las|los|en|para|[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñü]*))*)"
)
# What cannot be the unit a career belongs to, although it is written like one.
_NO_ES_UNIDAD = re.compile(
    r"(?i)^(?:escuela|instituto) (?:de )?(?:verano|invierno|posgrado|idiomas|lenguas)\b|"
    r"secundari|preuniversitari|\bnivel medio\b|\bcolegio\b"
)
# Connecting words the name may not end on: "Facultad de Ciencias y" is a cut.
_COLA = re.compile(r"(?:[ ,]+(?:y|e|de|del|la|las|los|en|para))+$")
# The university after the unit: "Instituto de Ciencias de la Salud de la
# UNAJ", "Facultad de Derecho Universidad Nacional de Córdoba".
_DE_LA_UNIVERSIDAD = re.compile(
    r"\s+(?:(?:de|del)\s+(?:la\s+)?)?(?:Universidad\b.*|[A-Z]{2,}\S*$)")


@dataclass(frozen=True)
class Unidad:
    nombre: str
    tipo: str


def _unidades_en(texto: str) -> list[Unidad]:
    encontradas = []
    for match in _UNA_UNIDAD.finditer(clean_text(texto)):
        nombre = _DE_LA_UNIVERSIDAD.sub("", clean_text(match.group(0)))
        nombre = _COLA.sub("", nombre).strip(" ,")
        if len(nombre.split()) < 3 or _NO_ES_UNIDAD.search(nombre):
            continue
        encontradas.append(Unidad(nombre, _TIPOS[match.group(1).lower()]))
    return encontradas


def _palabras(nombre: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", comparison_key(nombre))


def conocida(unidad: Unidad, conocidas: list[str]) -> str | None:
    """The unit the university published that this one is, if any.

    "Facultad de Ciencias Médicas" is the published "Ciencias Médicas", and
    "Escuela de Negocios" the published "Negocios": the published name may
    leave out the type.
    """
    propias = _palabras(unidad.nombre)
    sin_tipo = propias[2:] if len(propias) > 2 and propias[1] in {"de", "del", "en"} else propias
    for nombre in conocidas:
        otra = _palabras(nombre)
        if otra == propias or otra == sin_tipo or otra[-len(sin_tipo):] == sin_tipo and (
                len(otra) - len(sin_tipo) <= 2):
            return nombre
    return None


def _lugares(html: str) -> tuple[list[str], list[str], str]:
    """What a page says of itself: (title, site name and breadcrumb), its
    headings, and its body without menu, header and footer."""
    soup = BeautifulSoup(html, "html.parser")
    propios: list[str] = []
    if soup.title and soup.title.string:
        propios.append(soup.title.string)
    for meta in soup.find_all("meta", attrs={"property": "og:site_name"}):
        propios.append(meta.get("content") or "")
    for miga in soup.select(
            "[class*=breadcrumb], [id*=breadcrumb], [class*=migas], nav[aria-label*=readcrumb]"):
        propios.append(miga.get_text(" > "))
    for pie in soup.find_all(["footer", "nav", "header", "aside", "script", "style"]):
        pie.decompose()
    titulos = [h.get_text(" ") for h in soup.find_all(["h1", "h2"])[:4]]
    cuerpo = soup.find("main") or soup.body
    return propios, titulos, cuerpo.get_text("\n") if cuerpo else ""


def unidad_de_la_pagina(html: str, conocidas: list[str]) -> Unidad | None:
    """The unit a career page places the career in, or None when it does not
    say, or says two."""
    if not html:
        return None
    propios, titulos, cuerpo = _lugares(html)
    candidatas = [u for texto in propios for u in _unidades_en(texto)]
    candidatas += [u for texto in titulos for u in _unidades_en(texto)
                   if conocida(u, conocidas)]
    if not candidatas:
        return _del_cuerpo(cuerpo, conocidas)

    elegidas: dict[str, Unidad] = {}
    for unidad in candidatas:
        publicada = conocida(unidad, conocidas)
        nombre = publicada or unidad.nombre
        elegidas.setdefault(comparison_key(nombre), Unidad(nombre, unidad.tipo))
    if len(elegidas) != 1:
        return None
    return next(iter(elegidas.values()))


def _del_cuerpo(cuerpo: str, conocidas: list[str]) -> Unidad | None:
    nombradas = [line for texto in cuerpo.split("\n") for line in _unidades_en(texto)]
    distintas = {conocida(u, conocidas) or comparison_key(u.nombre) for u in nombradas}
    if len(distintas) != 1 or len(nombradas) < 2:
        return None
    unidad = nombradas[0]
    publicada = conocida(unidad, conocidas)
    if conocidas and not publicada:
        # The university published its units and the page names none of
        # them: what it names belongs to someone else.
        return None
    return Unidad(publicada or unidad.nombre, unidad.tipo)


_VACIAS = frozenset("de del la las los el y e en a con para por licenciatura "
                    "tecnicatura carrera ingenieria".split())


def es_la_pagina_de(html: str, carrera: str) -> bool:
    """Whether the page's title or main heading names the career: most of
    the words of its name, leaving out "Licenciatura en" and the like."""
    soup = BeautifulSoup(html or "", "html.parser")
    lugares = [soup.title.string if soup.title and soup.title.string else ""]
    lugares += [h.get_text(" ") for h in soup.find_all("h1")[:2]]
    texto = set(_palabras(" ".join(lugares)))
    propias = [p for p in _palabras(carrera) if p not in _VACIAS] or _palabras(carrera)
    return sum(p in texto for p in propias) * 2 >= len(propias) + (len(propias) > 1)
