"""The careers of the Universidad Nacional de Cuyo, from its catalogue.

``uncuyo.edu.ar/estudios/grado`` lists every grado and pregrado career as a
card with the name it is known by, its official name when it differs, the
unit that teaches it as the site abbreviates it and the link to its page:

    <span class="nombre_corto">Tecnicatura en Quirófano</span>
    <span class="nombre">Tecnicatura Universitaria en Quirófano</span>
    <span class="facultad">Cs. Médicas</span>

The card does not say where a career is taught: the Facultad de Ciencias
Aplicadas a la Industria is in San Rafael, the rest mostly in Mendoza, and
which is which the catalogue does not say.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from rumbo_scraper.normalizers.text import clean_text
from rumbo_scraper.parsers.unc import CarreraDeLaGuia

CATALOGO = "https://www.uncuyo.edu.ar/estudios/grado"
_PREGRADO = re.compile(r"(?i)^(?:tecnicatura|t[ée]cnic[oa])\b")
_CICLO = re.compile(r"(?i)^ciclo\b")


def nombre_de_la_unidad(texto: str) -> str:
    """"Cs. Médicas" -> "Facultad de Ciencias Médicas", "Inst. Balseiro" ->
    "Instituto Balseiro"."""
    nombre = re.sub(r"\bCs\.\s*", "Ciencias ", clean_text(texto))
    if nombre.startswith("Inst."):
        return clean_text(re.sub(r"^Inst\.\s*", "Instituto ", nombre))
    return "Facultad de " + nombre


def leer_catalogo(html: str, pagina: str = CATALOGO) -> list[CarreraDeLaGuia]:
    carreras = []
    for tarjeta in BeautifulSoup(html or "", "html.parser").select("div.card-estudio"):
        enlace = tarjeta.select_one("h3.card-title a[href]")
        corto = tarjeta.select_one("span.nombre_corto")
        oficial = tarjeta.select_one("span.nombre")
        facultad = tarjeta.select_one("span.facultad")
        if not enlace or not corto or not facultad:
            continue
        nombres = [clean_text(n.get_text(" ")) for n in (oficial, corto) if n]
        # A completion cycle takes a student who holds a degree already.
        if any(_CICLO.match(n) for n in nombres):
            continue
        nombre = nombres[0]
        unidad = nombre_de_la_unidad(facultad.get_text(" "))
        carreras.append(CarreraDeLaGuia(
            nombre, unidad, "Instituto" if unidad.startswith("Instituto") else "Facultad",
            urljoin(pagina, enlace["href"].strip()),
            "Pregrado" if _PREGRADO.match(nombre) else "Grado"))
    return carreras


# The plan on a career's page: "Plan de estudios:", then each year ("Primer
# Año", ..., "Quinta año" as one page writes it), each term, and the
# subjects one per line, until the degree it awards ("Al finalizar la carrera
# obtendrás el título de:").
_INICIO_DEL_PLAN = re.compile(r"(?i)^plan de estudios:?$")
_ANIO = re.compile(r"(?i)^(primer|segund|tercer|cuart|quint|sext)[oa]?\s+a[ñn]o$")
_ANIOS = {"primer": 1, "segund": 2, "tercer": 3, "cuart": 4, "quint": 5, "sext": 6}
_PERIODO = re.compile(r"(?i)^(?:primer|segundo)\s+(?:semestre|cuatrimestre)$|^anual(?:es)?$")
_FIN_DEL_PLAN = re.compile(r"(?i)^(?:al finalizar|normativa|unidad acad[ée]mica|otras carreras|inscripciones)")


def leer_plan(html: str) -> list[tuple[str, int]]:
    soup = BeautifulSoup(html or "", "html.parser")
    for parte in soup.find_all(["script", "style", "nav", "header", "footer"]):
        parte.decompose()
    materias: list[tuple[str, int]] = []
    dentro, anio = False, None
    for linea in soup.get_text("\n").split("\n"):
        linea = clean_text(linea)
        if not linea:
            continue
        if _INICIO_DEL_PLAN.match(linea):
            dentro = True
            continue
        if not dentro:
            continue
        if _FIN_DEL_PLAN.match(linea):
            break
        encabezado = _ANIO.match(linea)
        if encabezado:
            anio = _ANIOS[encabezado.group(1).lower()]
            continue
        if _PERIODO.match(linea) or not anio or linea.endswith(":") or len(linea) > 120:
            continue
        if linea not in [m for m, _ in materias]:
            materias.append((linea, anio))
    return materias
